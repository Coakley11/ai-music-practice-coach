"""Read-only song editing lifecycle knowledge — catalog, custom, lyrics, chords, persistence."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from music_coach_ami.app_knowledge import FEATURES
from music_coach_ami.types import CoachContext


@dataclass(frozen=True)
class SongEditingClassification:
    submode: str
    song_source: str = "unknown"
    edit_target: str = ""
    save_mode: str = ""
    persistence_scope: str = ""
    ownership_model: str = ""
    editor_feature: str = ""
    reopen_path: str = ""


_CATALOG_CHART = FEATURES["chart_editor"]
_CATALOG_LYRICS = FEATURES["lyrics_editor"]
_CUSTOM = FEATURES["custom_progression"]
_CATALOG = FEATURES["song_catalog"]
_PRACTICE_KEY = FEATURES["practice_key"]


def extract_song_edit_entities(low: str) -> tuple[str, str]:
    """Return (edit_target, song_source_hint)."""
    text = str(low or "").lower()
    target = ""
    if any(p in text for p in ("lyric", "lyrics", "cues")):
        target = "lyrics"
    elif any(p in text for p in ("chord", "progression", "chart")):
        target = "chords"
    elif "practice key" in text or ("key" in text and "original" not in text and "edit" not in text):
        target = "key"
    source = ""
    if any(p in text for p in ("custom song", "custom progression", "my custom", "created a custom", "my song")):
        source = "custom"
    elif any(p in text for p in ("catalog", "catalog song", "song in the catalog", "curated")):
        source = "catalog"
    return target, source


def is_song_editing_question(low: str) -> bool:
    text = str(low or "").lower()
    if "practice key" in text and any(p in text for p in ("edit", "chord", "difference", "vs", "versus", "compare")):
        return False
    markers = (
        "edit a song",
        "songs in the catalog",
        "in the catalog",
        "have to edit all the chords",
        "edit song",
        "edit the song",
        "edit my song",
        "edit lyrics",
        "add lyrics",
        "save lyrics",
        "save the lyrics",
        "changed a chord",
        "change a chord",
        "save the change",
        "save chord",
        "save my chord",
        "edit chord",
        "edit chords",
        "change the chords",
        "change chords",
        "custom song",
        "custom progression",
        "catalog song",
        "song catalog",
        "my version",
        "original or just my",
        "edited a song",
        "edited yesterday",
        "get back to it",
        "continue editing",
        "where are my custom songs",
        "save to library",
        "lyrics editor",
        "edit song chart",
        "song chart",
        "typed new lyrics",
        "still there tomorrow",
        "saved automatically",
        "autosave",
        "editable version",
        "duplicate",
        "personal copy",
        "create a custom song",
        "rename my custom",
        "delete it",
        "sign out",
        "permanently transpose",
        "practice in e",
        "practice key permanently",
        "original key",
        "where do i change the chords",
        "how do i add lyrics",
    )
    return any(p in text for p in markers)


def classify_song_editing_question(low: str, ctx: CoachContext | None = None) -> SongEditingClassification:
    text = str(low or "").lower()
    ctx = ctx or CoachContext()
    edit_target, source_hint = extract_song_edit_entities(text)
    active_pick = str(ctx.active_song_pick_key or "").lower()
    if not source_hint:
        if active_pick.startswith("custom::") or "custom" in str(ctx.extra.get("active_music_source", "")).lower():
            source_hint = "custom"
        elif ctx.active_song_title or active_pick:
            source_hint = "catalog"

    if any(p in text for p in ("catalog song", "original or just my", "my version", "change the original", "for everyone", "songs in the catalog", "in the catalog")):
        return SongEditingClassification(
            submode="catalog_ownership",
            song_source="catalog",
            edit_target=edit_target or "general",
            save_mode="explicit_sidecar",
            persistence_scope="workspace_user_files",
            ownership_model="sidecar_override",
            editor_feature="chart_editor,lyrics_editor",
        )

    if any(
        p in text
        for p in (
            "have to edit all the chords",
            "practice in e",
            "practice in eb",
            "practice in e b",
            "practice in e flat",
        )
    ) or (
        "practice key" in text
        and any(p in text for p in ("permanent", "transpose", "still be transposed"))
    ):
        return SongEditingClassification(
            submode="practice_key_only",
            song_source=source_hint or "catalog",
            edit_target="key",
            save_mode="per_source_practice_key",
            persistence_scope="workspace_practice_key_by_source",
            ownership_model="practice_transposition_not_chart_edit",
            editor_feature="practice_key",
        )

    if any(p in text for p in ("edited yesterday", "get back to it", "continue editing", "where are the songs i edited", "where did my changes go")):
        reopen = (
            "Custom Progression → **Load saved or demo charts** → **Saved songs** → **Load selected**, "
            "or reopen the same catalog song in **Song Selection** (your saved overrides reload automatically)."
        )
        if source_hint == "custom":
            reopen = (
                "Studio sidebar → **Custom Progression** → expand **Load saved or demo charts**, "
                "choose your song under **Saved songs**, then click **Load selected**."
            )
        return SongEditingClassification(
            submode="return_later",
            song_source=source_hint or "mixed",
            edit_target=edit_target or "general",
            save_mode="library_or_sidecar",
            persistence_scope="workspace_and_cloud_envelope",
            ownership_model="user_owned_edits",
            reopen_path=reopen,
        )

    if edit_target == "lyrics" or any(p in text for p in ("add lyrics", "save lyrics", "typed new lyrics", "lyrics saved")):
        return SongEditingClassification(
            submode="lyrics_save",
            song_source=source_hint or "catalog",
            edit_target="lyrics",
            save_mode="explicit_save_button",
            persistence_scope="user_song_content_json",
            ownership_model="user_sidecar",
            editor_feature="lyrics_editor",
            reopen_path="Song Selection → select the same song → **Lyrics & Cues**",
        )

    if edit_target == "chords" or any(
        p in text for p in ("changed a chord", "save the change", "save chord", "save corrected", "edit song chart")
    ):
        return SongEditingClassification(
            submode="chord_save",
            song_source=source_hint or "catalog",
            edit_target="chords",
            save_mode="explicit_save_button",
            persistence_scope="user_chart_overrides_json",
            ownership_model="user_sidecar",
            editor_feature="chart_editor",
            reopen_path="Song Selection → select the same song → **Edit Song Chart**",
        )

    if any(p in text for p in ("custom song", "created a custom", "where are my custom", "create a custom song")):
        return SongEditingClassification(
            submode="custom_reopen_edit",
            song_source="custom",
            edit_target=edit_target or "chords",
            save_mode="save_to_library",
            persistence_scope="cpl_saved_progressions_and_cloud",
            ownership_model="user_owned_custom_progression",
            editor_feature="custom_progression",
            reopen_path=(
                "Studio sidebar → **Custom Progression** → **Load saved or demo charts** → "
                "**Saved songs** → **Load selected**"
            ),
        )

    if any(p in text for p in ("edit a song", "edit song", "change the progression", "where do i change")):
        return SongEditingClassification(
            submode="general_edit",
            song_source=source_hint or "catalog",
            edit_target=edit_target or "general",
            save_mode="depends_on_source",
            persistence_scope="workspace",
            ownership_model="sidecar_or_custom_library",
            editor_feature="chart_editor,custom_progression,lyrics_editor",
        )

    return SongEditingClassification(
        submode="general_edit",
        song_source=source_hint,
        edit_target=edit_target,
    )


def _lifecycle_steps(
    *,
    use: str,
    go_to: str,
    change: str,
    save: str,
    important: str = "",
) -> list[str]:
    steps = [
        f"**Use:** {use}",
        f"**Go to:** {go_to}",
        f"**Change:** {change}",
        f"**Save:** {save}",
    ]
    if important:
        steps.append(f"**Important:** {important}")
    return steps


def compose_song_editing_answer(
    classification: SongEditingClassification,
    ctx: CoachContext | None = None,
) -> dict[str, Any]:
    ctx = ctx or CoachContext()
    sub = classification.submode
    song = str(ctx.active_song_title or "").strip()

    if sub == "catalog_ownership":
        body = (
            "Editing a **catalog song** does **not** change the shared curated catalog for everyone. "
            "Your chord and lyric edits are stored in **your workspace sidecar files** and merged when you "
            "reopen that song."
        )
        steps = _lifecycle_steps(
            use="Song Selection editors (catalog songs)",
            go_to="Studio sidebar → **Song Selection** → **Edit Song Chart** or **Lyrics & Cues**",
            change="Chord edits in **Edit Song Chart**; lyrics/performance cues in **Lyrics & Cues**.",
            save=(
                "Explicit save only — **Save corrected chart** / **Save as user verified** for chords; "
                "**Save Lyrics & Cues** for lyrics. Typing alone does not write to disk."
            ),
            important=(
                "There is no separate “duplicate song” action. You keep the original catalog chart available "
                "via **Revert to catalog** or **Revert my lyrics**. "
                "The app does not publish your edits back to the shared catalog."
            ),
        )
        nxt = "Open the song in Song Selection, make your edit, then click the explicit Save button for that editor."
        return {"direct_answer": body, "app_navigation_steps": steps, "suggested_next_action": nxt}

    if sub == "practice_key_only":
        body = (
            "You usually **do not** need to rewrite every chord. Change the sidebar **Practice / Concert Key** "
            "to read and practice in another key without editing the saved chart."
        )
        steps = _lifecycle_steps(
            use="Practice / Concert Key (temporary transposition)",
            go_to="Global studio bar → **Practice / Concert Key** (sidebar when visible)",
            change="Pick the concert key you want to read/practice in today.",
            save="Saved per song source in your workspace (`practice_key_by_source`); it transposes display/practice, not the underlying chart.",
            important=(
                "This is **not** the same as **Edit Song Chart**. Practice Key does not replace saved chord changes. "
                "Backing uses your practice context; it does not rewrite the stored progression."
            ),
        )
        nxt = "Use **Practice / Concert Key** for today’s key; use **Edit Song Chart** only when the harmony itself should change permanently."
        return {"direct_answer": body, "app_navigation_steps": steps, "suggested_next_action": nxt}

    if sub == "return_later":
        body = "Your edited material returns through the same place you saved it — custom songs from the Custom Progression library, catalog edits when you reopen that song in Song Selection."
        custom_path = (
            "Studio sidebar → **Custom Progression** → **Load saved or demo charts** → "
            "**Saved songs** → **Load selected** → **Set as Active Song** if you want it across Practice/Backing."
        )
        catalog_path = (
            "Studio sidebar → **Song Selection** → choose the same catalog song. "
            "Saved chart/lyric overrides reload from your workspace automatically."
        )
        steps = _lifecycle_steps(
            use="Saved custom songs or catalog sidecar overrides",
            go_to=custom_path if classification.song_source == "custom" else f"{custom_path}\n\nOr for catalog edits:\n{catalog_path}",
            change="Continue editing chords on **Custom Progression** or **Edit Song Chart** / lyrics in **Lyrics & Cues**.",
            save="Custom songs: **Save to library**. Catalog edits: explicit chart/lyrics Save buttons you used before.",
            important=(
                "Workspace/cloud restore brings back your active song, custom library, and saved overrides after refresh. "
                "There is no separate hidden “Projects” list beyond Song Selection + Custom Progression library."
            ),
        )
        nxt = "Load the saved custom song from Custom Progression, or reopen the catalog song in Song Selection to continue."
        return {"direct_answer": body, "app_navigation_steps": steps, "suggested_next_action": nxt}

    if sub == "lyrics_save":
        body = (
            "Catalog song lyrics and performance cues live in **Lyrics & Cues** on Song Selection. "
            "You must click **Save Lyrics & Cues** — lyrics are **not** autosaved to disk while you type."
        )
        steps = _lifecycle_steps(
            use=_CATALOG_LYRICS.display_name,
            go_to=_CATALOG_LYRICS.navigation_path,
            change="Edit section lyrics and cues in the **Lyrics & Cues** panel (Karaoke also links here for Voice).",
            save="Click **Save Lyrics & Cues** (or **Save as user verified**). Status shows **Unsaved changes** until you save.",
            important=(
                "Custom Progression lyrics save code exists but the CPL lyrics panel is **not mounted in the current UI** — "
                "use Song Selection for catalog songs. **Revert my lyrics** restores the catalog text."
            ),
        )
        nxt = "After editing, click **Save Lyrics & Cues** so the lyrics are still there tomorrow."
        return {"direct_answer": body, "app_navigation_steps": steps, "suggested_next_action": nxt}

    if sub == "chord_save":
        body = (
            "There is **no generic Save button** on the song page — chord changes save from **Edit Song Chart** "
            "after you enable editing."
        )
        steps = _lifecycle_steps(
            use=_CATALOG_CHART.display_name,
            go_to=_CATALOG_CHART.navigation_path,
            change="Turn on **Enable editing**, edit bar/section chords in the song's written key, then review the draft.",
            save="Click **Save corrected chart** or **Save as user verified**. Use **Revert to catalog** to discard your override.",
            important="Saved overrides live in your workspace (`user_chart_overrides.json`) and persist when you reopen the song.",
        )
        nxt = "Enable editing, make the chord change, then click **Save corrected chart**."
        return {"direct_answer": body, "app_navigation_steps": steps, "suggested_next_action": nxt}

    if sub == "custom_reopen_edit":
        body = (
            "Custom songs you built before live in the **Custom Progression** library. "
            "Load one, edit its sections/chords on the same page, then save back to the library."
        )
        steps = _lifecycle_steps(
            use=_CUSTOM.display_name,
            go_to=classification.reopen_path or _CUSTOM.navigation_path,
            change="After loading, edit sections/chords in the Custom Progression builder; set **Original Key**, meter, BPM as needed.",
            save=(
                "**Save to library** stores a named custom song (session draft also persists across refresh via workspace restore). "
                "Use **Set as Active Song** to practice/back it elsewhere in the studio."
            ),
            important="Custom songs are user-owned (`custom::` pick keys). Delete via **More options → Delete saved progression**.",
        )
        nxt = "Load your saved song, edit it, click **Save to library**, then **Set as Active Song** if you want to practice it now."
        return {"direct_answer": body, "app_navigation_steps": steps, "suggested_next_action": nxt}

    # general_edit fallback
    src_line = "catalog song in **Song Selection**" if classification.song_source != "custom" else "custom song in **Custom Progression**"
    body = f"Song editing depends on whether you are working on a {src_line}."
    steps = _lifecycle_steps(
        use="Song Selection (catalog) or Custom Progression (your own songs)",
        go_to="**Song Selection** → **Edit Song Chart** / **Lyrics & Cues**, or **Custom Progression** for songs you created",
        change="Charts/lyrics for catalog songs; full progression structure for custom songs.",
        save="Catalog: explicit Save buttons in each editor. Custom: **Save to library**.",
    )
    return {
        "direct_answer": body,
        "app_navigation_steps": steps,
        "suggested_next_action": "Pick the editor that matches what you want to change, then use its real Save control.",
    }


def song_editing_diagnostics(
    classification: SongEditingClassification,
    ctx: CoachContext | None = None,
) -> dict[str, Any]:
    ctx = ctx or CoachContext()
    return {
        "song_edit_submode": classification.submode,
        "song_source_type": classification.song_source,
        "edit_target": classification.edit_target,
        "editor_feature": classification.editor_feature,
        "save_mode": classification.save_mode,
        "persistence_scope": classification.persistence_scope,
        "ownership_model": classification.ownership_model,
        "reopen_path": classification.reopen_path,
        "active_song_title": ctx.active_song_title or None,
        "active_song_pick_key": ctx.active_song_pick_key or None,
        "app_knowledge_consulted": "song_editing_knowledge,"
        + ",".join(
            x
            for x in (
                classification.editor_feature,
                "song_catalog",
                "practice_key",
            )
            if x
        ),
    }
