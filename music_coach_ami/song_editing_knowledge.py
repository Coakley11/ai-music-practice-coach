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

_NAMED_KEY_IN_RE = re.compile(
    r"\bin\s+"
    r"(?:"
    r"[a-g](?:\s*(?:flat|sharp|b|#|♭|♯))?(?:\s*(?:major|minor|min|maj|m))?"
    r"|e[\s-]?(?:flat|b)|b[\s-]?(?:flat|b)|a[\s-]?(?:flat|b)|d[\s-]?(?:flat|b)|"
    r"g[\s-]?(?:flat|b)|f[\s-]?(?:flat|b)|c[\s-]?(?:flat|b)"
    r")",
    re.I,
)
_PRACTICE_PLAY_IN_KEY_RE = re.compile(
    r"\b(?:practice|play|rehears(?:e|al)?)\s+.+\s+in\s+",
    re.I,
)


def _has_named_key_reference(text: str) -> bool:
    return bool(_NAMED_KEY_IN_RE.search(str(text or "")))


def _is_persistent_chord_edit_question(text: str) -> bool:
    """Persistent chart/harmony rewrite — beats non-destructive Practice Key semantics."""
    low = str(text or "").lower()
    if re.search(r"\b(?:do i|should i|have to|need to)\s+(?:rewrite|edit)\b", low):
        return False
    if any(
        p in low
        for p in (
            "permanently replace",
            "permanently rewrite",
            "permanently change",
            "from now on",
            "correct the chord",
            "replace one chord",
            "replace the first chord",
            "replace the chord",
            "rewrite progression",
            "rewrite this progression",
            "rewrite the progression",
            "rewrite the chords",
            "saved harmony",
            "change the actual chart",
            "saved progression to be",
            "edit song chart",
            "save corrected chart",
        )
    ):
        if ("practice key" in low or "concert key" in low) and any(
            p in low for p in ("permanent", "permanently")
        ):
            if not any(
                p in low
                for p in (
                    "replace",
                    "rewrite",
                    "correct the chord",
                    "first chord",
                    "verse",
                    "chorus",
                    "saved progression to be",
                )
            ):
                return False
        return True
    return False


def _is_practice_in_named_key_question(text: str) -> bool:
    """Practice/play an existing song in a named key without rewriting the saved chart."""
    low = str(text or "").lower()
    if _is_persistent_chord_edit_question(low):
        return False
    if not _has_named_key_reference(low):
        return False
    practice_play = re.search(r"\b(?:practice|play|rehears(?:e|al))\b", low)
    scope_markers = (
        "today",
        "for practice",
        "for rehearsal",
        "without changing the song",
        "without changing",
        "do i need to edit",
        "do i have to edit",
        "need to edit the chord",
        "need to edit the chords",
        "have to edit",
        "rewrite the chord",
        "transpose the saved",
        "only want",
        "for today's",
        "for now",
        "this song",
    )
    if _PRACTICE_PLAY_IN_KEY_RE.search(low):
        return True
    if re.search(r"\bonly\s+(?:want\s+)?this\s+in\s+", low):
        return True
    if practice_play and any(p in low for p in scope_markers):
        return True
    if re.search(r"\b(?:want|need)\s+(?:to\s+)?(?:practice|play)\b", low) and any(p in low for p in scope_markers):
        return True
    return False


def _extract_practice_key_label(text: str) -> str:
    m = _NAMED_KEY_IN_RE.search(str(text or ""))
    if not m:
        return ""
    return re.sub(r"^\s*in\s+", "", m.group(0).strip(), flags=re.I).strip()


def _extract_practice_song_phrase(text: str) -> str:
    low = str(text or "")
    m = re.search(
        r"\b(?:practice|play|rehears(?:e|al)?)\s+(.+?)\s+in\s+",
        low,
        flags=re.I,
    )
    if not m:
        return ""
    phrase = m.group(1).strip(" .,")
    if phrase.lower() in {"this song", "this", "the song"}:
        return ""
    return phrase


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


def is_practice_key_editing_semantics_question(low: str) -> bool:
    """Non-destructive Practice Key transposition vs persistent chart editing — not page comparison."""
    text = str(low or "").lower()
    if _is_persistent_chord_edit_question(text):
        return False
    if _is_practice_in_named_key_question(text):
        return True
    if "practice key" in text and any(
        p in text for p in ("chord", "edit", "chart", "difference", "vs", "versus", "compare", "permanent", "saved")
    ):
        return True
    if any(p in text for p in ("concert key", "transpose for practice", "without changing the song")):
        return True
    if any(p in text for p in ("practice in e", "practice in eb", "practice in e-flat", "practice in e flat", "practice in bb", "practice in b flat")):
        return True
    if re.search(r"practice (?:this )?song in\b", text) and any(
        p in text for p in ("chord", "edit", "key", "flat", "sharp", "today", "transpose")
    ):
        return True
    if "practice this song" in text and any(p in text for p in ("chord", "edit", "key", "flat", "today", "transpose")):
        return True
    if re.search(r"play this in\b", text) and any(p in text for p in ("chord", "edit", "key", "flat", "today", "transpose", "saved")):
        return True
    if "practice key" in text and any(p in text for p in ("permanent", "permanently", "still be transposed", "rewrite")):
        return True
    if any(p in text for p in ("should i practice this in", "practice in bb today", "practice in b flat today")) and any(
        p in text for p in ("edit", "chord", "transpose", "saved song", "without changing")
    ):
        return True
    return False


def is_song_editing_question(low: str) -> bool:
    text = str(low or "").lower()
    if is_practice_key_editing_semantics_question(text):
        return True
    markers = (
        "edit a song",
        "songs in the catalog",
        "in the catalog",
        "have to edit all the chords",
        "need to edit the chord",
        "need to edit the chords",
        "do i need to edit",
        "practice this song in",
        "without changing the song",
        "permanently replace",
        "permanently change",
        "permanently rewrite",
        "rewrite this progression",
        "rewrite the progression",
        "changing the practice key",
        "change practice key",
        "haven't pressed save",
        "haven't saved",
        "didn't save",
        "close the app",
        "still be there if i close",
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

    if (
        ("practice key" in text or "concert key" in text)
        and any(p in text for p in ("chord", "edit", "chart", "changing"))
        and any(p in text for p in ("difference", " vs ", " versus ", "compare", "what's the difference"))
    ) or (
        "practice key" in text
        and any(p in text for p in ("edit", "chord", "chart"))
        and any(p in text for p in ("difference", " vs ", " versus ", "compare"))
    ):
        return SongEditingClassification(
            submode="practice_key_vs_chord_edit",
            song_source=source_hint or "catalog",
            edit_target="key_vs_chords",
            save_mode="practice_key_or_explicit_chart_save",
            persistence_scope="practice_key_by_source_or_chart_override",
            ownership_model="temporary_transposition_vs_persistent_chart_edit",
            editor_feature="practice_key,chart_editor",
        )

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

    if _is_persistent_chord_edit_question(text):
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

    if is_practice_key_editing_semantics_question(text) and not any(
        p in text for p in ("difference between", " vs ", " versus ", "compare")
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
        p in text for p in (
            "changed a chord",
            "save the change",
            "save chord",
            "save corrected",
            "edit song chart",
        )
    ):
        if _is_practice_in_named_key_question(text) or (
            is_practice_key_editing_semantics_question(text)
            and not _is_persistent_chord_edit_question(text)
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
    *,
    question: str = "",
) -> dict[str, Any]:
    ctx = ctx or CoachContext()
    sub = classification.submode
    song = str(ctx.active_song_title or "").strip()
    text = str(question or "").lower()

    if sub == "catalog_ownership":
        body = (
            "**No — your saved edits do not change the original catalog song.** "
            "The curated version stays as it was for everyone. "
            "Your chord and lyric changes are kept separately and appear again when you reopen that song."
        )
        steps = _lifecycle_steps(
            use="Song Selection editors (catalog songs)",
            go_to="Studio sidebar → **Song Selection** → **Edit Song Chart** or **Lyrics & Cues**",
            change="Chord edits in **Edit Song Chart**; lyrics and performance cues in **Lyrics & Cues**.",
            save=(
                "Click **Save corrected chart** or **Save as user verified** for chords; "
                "**Save Lyrics & Cues** for lyrics. Your changes are not saved until you click Save."
            ),
            important=(
                "There is no separate duplicate-song action. "
                "Use **Revert to catalog** or **Revert my lyrics** to go back to the original catalog version."
            ),
        )
        nxt = "Open the song in Song Selection, make your edit, then click Save in that editor."
        return {"direct_answer": body, "app_navigation_steps": steps, "suggested_next_action": nxt}

    if sub == "practice_key_vs_chord_edit":
        body = (
            "**Practice Key** changes how the song is transposed for practice without changing the saved song chart.\n\n"
            "**Editing the song's chords** changes the saved harmony itself. "
            "For a catalog song, that becomes your saved chart after you click **Save corrected chart** in **Edit Song Chart**.\n\n"
            "**Use Practice Key when** you only want to play the same song in another key.\n\n"
            "**Edit the chords when** you want to correct or rewrite the progression permanently.\n\n"
            "**Important:** Practice Key may be remembered for that song, but it does **not** rewrite the saved chart."
        )
        steps = _lifecycle_steps(
            use="**Practice / Concert Key** for practice transposition, or **Edit Song Chart** for permanent harmony changes",
            go_to=(
                "Global studio bar → **Practice / Concert Key** for non-destructive practice transposition; "
                "or **Song Selection** → **Edit Song Chart** to change saved chords"
            ),
            change="Pick a concert key to read/practice in, or edit bar/section chords in the chart editor.",
            save=(
                "Practice Key can be remembered for that song when you return, without changing the saved chart. "
                "Chart edits require **Save corrected chart** or **Save as user verified**."
            ),
        )
        nxt = "Use **Practice / Concert Key** for a different practice key; use **Edit Song Chart** only when the harmony itself should change."
        return {"direct_answer": body, "app_navigation_steps": steps, "suggested_next_action": nxt}

    if sub == "practice_key_only":
        song_phrase = _extract_practice_song_phrase(text) or song
        key_label = _extract_practice_key_label(text)
        asking_about_practice_key = ("practice key" in text or "concert key" in text) and any(
            p in text for p in ("permanent", "permanently", "change the key of my song", "transpose the saved")
        )
        if asking_about_practice_key:
            body = (
                "**No. Changing Practice / Concert Key does not permanently rewrite your song.** "
                "It changes the key you read and hear for practice while leaving the saved chart unchanged."
            )
        elif song_phrase and key_label:
            body = (
                f"**No. If you only want to practice {song_phrase} in {key_label}, "
                "change the Practice / Concert Key instead of editing the song's chords.**"
            )
        else:
            body = (
                "**No. Change the Practice / Concert Key instead of editing the song's chords.** "
                "You do **not** need to rewrite every chord if you only want to play this song in another key."
            )
        change_line = f"Choose **{key_label}**." if key_label else "Pick the concert key you want to read and practice in."
        steps = _lifecycle_steps(
            use="Practice / Concert Key (non-destructive practice transposition)",
            go_to="Global studio bar → **Practice / Concert Key** (sidebar when visible)",
            change=change_line,
            save=(
                "Your chosen practice key can be remembered for that song, so charts and playback read in that key "
                "when you return — without changing the saved song chart."
            ),
            important=(
                "This is **not** the same as **Edit Song Chart**. Practice Key transposes what you see and hear "
                "for practice; it does not replace saved chord edits."
            ),
        )
        nxt = (
            "Set **Practice / Concert Key** for your practice key; use **Edit Song Chart** only when you actually "
            "want to correct or permanently rewrite the song's harmony."
        )
        return {"direct_answer": body, "app_navigation_steps": steps, "suggested_next_action": nxt}

    if sub == "return_later":
        body = (
            "Reopen the song from the same place you saved it — "
            "your custom songs in **Custom Progression**, or the same catalog song in **Song Selection**."
        )
        custom_path = (
            "Studio sidebar → **Custom Progression** → **Load saved or demo charts** → "
            "**Saved songs** → **Load selected** → **Set as Active Song** if you want it across Practice/Backing."
        )
        catalog_path = (
            "Studio sidebar → **Song Selection** → choose the same catalog song. "
            "Your saved chart and lyric changes appear again automatically."
        )
        steps = _lifecycle_steps(
            use="Saved custom songs or saved catalog edits",
            go_to=custom_path if classification.song_source == "custom" else f"{custom_path}\n\nOr for catalog edits:\n{catalog_path}",
            change="Continue editing chords on **Custom Progression** or **Edit Song Chart** / lyrics in **Lyrics & Cues**.",
            save="Custom songs: **Save to library**. Catalog edits: the same Save buttons in **Edit Song Chart** or **Lyrics & Cues**.",
            important=(
                "Saved songs and saved edits are available again when you return to the app. "
                "There is no separate hidden Projects list beyond Song Selection and your Custom Progression library."
            ),
        )
        nxt = "Load your saved custom song from Custom Progression, or reopen the catalog song in Song Selection to continue."
        return {"direct_answer": body, "app_navigation_steps": steps, "suggested_next_action": nxt}

    if sub == "lyrics_save":
        unsaved_close = any(
            p in text
            for p in (
                "haven't pressed save",
                "haven't saved",
                "didn't save",
                "close the app",
                "still be there if i close",
                "typed new lyrics but",
            )
        )
        if classification.song_source == "custom":
            body = (
                "**Custom Progression does not currently expose a lyrics editor in the UI.** "
                "For catalog songs, use **Lyrics & Cues** on Song Selection."
            )
            steps = _lifecycle_steps(
                use="Lyrics & Cues (catalog songs only today)",
                go_to=_CATALOG_LYRICS.navigation_path,
                change="Edit section lyrics and cues in the **Lyrics & Cues** panel.",
                save="Click **Save Lyrics & Cues** so your lyrics are still there when you return.",
            )
            nxt = "Open a catalog song in Song Selection and use **Lyrics & Cues** if you need editable lyrics today."
            return {"direct_answer": body, "app_navigation_steps": steps, "suggested_next_action": nxt}
        if unsaved_close:
            body = (
                "**No — don't rely on unsaved lyrics surviving after you leave or close the app.** "
                "Click **Save Lyrics & Cues** first."
            )
        else:
            body = (
                "Open **Lyrics & Cues** on Song Selection, edit your lyrics, then click **Save Lyrics & Cues**. "
                "Lyrics are **not** saved automatically while you type."
            )
        steps = _lifecycle_steps(
            use=_CATALOG_LYRICS.display_name,
            go_to=_CATALOG_LYRICS.navigation_path,
            change="Edit section lyrics and cues in the **Lyrics & Cues** panel (Karaoke also links here for Voice).",
            save="Click **Save Lyrics & Cues** (or **Save as user verified**). You'll see **Unsaved changes** until you save.",
            important="Use **Revert my lyrics** to restore the original catalog lyrics.",
        )
        nxt = "Click **Save Lyrics & Cues** before you leave so the lyrics are still there tomorrow."
        return {"direct_answer": body, "app_navigation_steps": steps, "suggested_next_action": nxt}

    if sub == "chord_save":
        body = (
            "Chord changes save from **Edit Song Chart** — turn on **Enable editing**, make your change, "
            "then click **Save corrected chart** or **Save as user verified**."
        )
        steps = _lifecycle_steps(
            use=_CATALOG_CHART.display_name,
            go_to=_CATALOG_CHART.navigation_path,
            change="Turn on **Enable editing**, edit bar/section chords in the song's written key, then review the draft.",
            save="Click **Save corrected chart** or **Save as user verified**. Use **Revert to catalog** to discard your changes.",
            important="After you save, your chord changes come back when you reopen that song. The original catalog chart stays available via **Revert to catalog**.",
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
                "Click **Save to library** when you're done so you can open this song again later. "
                "Use **Set as Active Song** to practice or back it elsewhere in the studio."
            ),
            important="Delete a saved custom song via **More options → Delete saved progression**.",
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
