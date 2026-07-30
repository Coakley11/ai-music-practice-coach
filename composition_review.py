"""Whole-song review helpers for Composition Studio (CS-B5)."""

from __future__ import annotations

from typing import Any, Literal

from composition_document import (
    COMPOSITION_PHASE_LABELS,
    ensure_workflow,
    harmonized_section_count,
    lyrics_section_count,
    melodized_section_count,
    ordered_sections,
    section_has_chords,
    section_has_lyrics,
    section_has_melody,
)
from composition_lyric_suggestions import collect_song_lyric_themes
from custom_progression_lab import format_entries_bar_line

ReadinessStatus = Literal["complete", "partial", "missing", "skipped", "current"]


def _status_rank(status: ReadinessStatus) -> int:
    return {"complete": 0, "current": 1, "partial": 2, "missing": 3, "skipped": 4}.get(status, 3)


def build_readiness_checklist(doc: dict[str, Any], *, current_phase: str = "review") -> list[dict[str, Any]]:
    wf = ensure_workflow(doc)
    skip_lyrics = bool(wf.get("skip_lyrics"))
    meta = doc.get("metadata") or {}
    origin = doc.get("origin") or {}
    idea = str(meta.get("description") or origin.get("seed_summary") or "").strip()
    genre = str(meta.get("style") or "").strip()

    sections = ordered_sections(doc)
    h_done, h_total = harmonized_section_count(doc)
    m_done, m_total = melodized_section_count(doc)
    l_done, l_total = lyrics_section_count(doc)

    def phase_status(phase: str, *, complete: bool, partial: bool, note: str) -> ReadinessStatus:
        if phase == current_phase:
            return "current"
        if complete:
            return "complete"
        if partial:
            return "partial"
        return "missing"

    vision_complete = bool(idea) and bool(genre)
    vision_partial = bool(idea) or bool(genre)

    structure_complete = len(sections) >= 2
    structure_partial = len(sections) == 1

    chords_complete = h_total > 0 and h_done == h_total
    chords_partial = h_done > 0 and h_done < h_total

    melody_complete = m_total > 0 and m_done == m_total
    melody_partial = m_done > 0 and m_done < m_total

    if skip_lyrics:
        lyrics_status: ReadinessStatus = "skipped"
        lyrics_note = "Instrumental — lyrics skipped"
    else:
        lyrics_complete = l_total > 0 and l_done == l_total
        lyrics_partial = l_done > 0 and l_done < l_total
        lyrics_status = phase_status(
            "lyrics",
            complete=lyrics_complete,
            partial=lyrics_partial,
            note="",
        )
        if lyrics_status == "complete":
            lyrics_note = f"{l_done}/{l_total} sections with lyrics"
        elif lyrics_status == "partial":
            lyrics_note = f"{l_done}/{l_total} sections — some still need words"
        else:
            lyrics_note = "No lyrics written yet"

    items: list[dict[str, Any]] = [
        {
            "phase": "vision",
            "label": COMPOSITION_PHASE_LABELS["vision"],
            "status": phase_status("vision", complete=vision_complete, partial=vision_partial, note=""),
            "note": "Genre and song idea captured" if vision_complete else "Add genre and a short song idea",
        },
        {
            "phase": "structure",
            "label": COMPOSITION_PHASE_LABELS["structure"],
            "status": phase_status(
                "structure",
                complete=structure_complete,
                partial=structure_partial,
                note="",
            ),
            "note": f"{len(sections)} section(s) in your form"
            if sections
            else "Add at least one section",
        },
        {
            "phase": "chords",
            "label": COMPOSITION_PHASE_LABELS["chords"],
            "status": phase_status("chords", complete=chords_complete, partial=chords_partial, note=""),
            "note": f"{h_done}/{h_total} sections harmonized"
            if h_total
            else "Harmonize your sections",
        },
        {
            "phase": "melody",
            "label": COMPOSITION_PHASE_LABELS["melody"],
            "status": phase_status("melody", complete=melody_complete, partial=melody_partial, note=""),
            "note": f"{m_done}/{m_total} sections with melodic ideas"
            if m_total
            else "Shape melody per section",
        },
        {
            "phase": "lyrics",
            "label": COMPOSITION_PHASE_LABELS["lyrics"],
            "status": lyrics_status,
            "note": lyrics_note,
        },
        {
            "phase": "review",
            "label": COMPOSITION_PHASE_LABELS["review"],
            "status": "current" if current_phase == "review" else "complete",
            "note": "Step back and listen to the whole song",
        },
    ]
    return items


def readiness_glyph(status: ReadinessStatus) -> str:
    return {
        "complete": "✓",
        "partial": "◐",
        "missing": "○",
        "skipped": "—",
        "current": "●",
    }.get(status, "○")


def song_is_ready(doc: dict[str, Any]) -> bool:
    checklist = build_readiness_checklist(doc)
    for row in checklist:
        if row["phase"] in ("review", "lyrics") and row["status"] == "skipped":
            continue
        if row["phase"] == "review":
            continue
        if row["status"] not in ("complete", "skipped"):
            return False
    return bool(ordered_sections(doc))


def harmony_overview_rows(doc: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sec in ordered_sections(doc):
        variant = str(sec.get("label_variant") or sec.get("label") or "Section")
        link = sec.get("chord_link") or {}
        linked = bool(link.get("linked"))
        source_id = str(link.get("source_section_id") or "")
        line = format_entries_bar_line(sec.get("chords") or [], max_chords=12)
        if not line or line == "(empty)":
            line = "(no chords yet)"
        note = ""
        if linked and source_id:
            from composition_document import section_by_id

            source = section_by_id(doc, source_id)
            src_label = str((source or {}).get("label_variant") or (source or {}).get("label") or "source")
            note = f"Shares harmony with {src_label}"
        rows.append(
            {
                "section_id": str(sec.get("id") or ""),
                "variant": variant,
                "line": line,
                "linked": linked,
                "note": note,
                "has_chords": section_has_chords(sec),
            }
        )
    return rows


def melody_overview_rows(doc: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sec in ordered_sections(doc):
        variant = str(sec.get("label_variant") or sec.get("label") or "Section")
        melody = sec.get("melody") or {}
        intent = melody.get("intent") or {}
        remember = str(intent.get("remember") or "").strip()
        hum = str(intent.get("hum_notes") or "").strip()
        phrases = [p for p in (melody.get("phrases") or []) if isinstance(p, dict)]
        summary = remember or hum or ""
        if not summary and phrases:
            summary = str(phrases[0].get("motif") or phrases[0].get("label") or "")
        rows.append(
            {
                "section_id": str(sec.get("id") or ""),
                "variant": variant,
                "complete": section_has_melody(sec),
                "summary": summary[:100] if summary else "",
            }
        )
    return rows


def lyrics_overview_rows(doc: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sec in ordered_sections(doc):
        variant = str(sec.get("label_variant") or sec.get("label") or "Section")
        lyrics = sec.get("lyrics") or {}
        raw = str(lyrics.get("raw_text") or "").strip()
        rows.append(
            {
                "section_id": str(sec.get("id") or ""),
                "variant": variant,
                "has_lyrics": section_has_lyrics(sec),
                "raw_text": raw,
            }
        )
    return rows


def _count_sections_by_label(doc: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for sec in ordered_sections(doc):
        label = str(sec.get("label") or "Section")
        counts[label] = counts.get(label, 0) + 1
    return counts


def coach_line_for_review(doc: dict[str, Any]) -> str:
    meta = doc.get("metadata") or {}
    origin = doc.get("origin") or {}
    idea = str(meta.get("description") or origin.get("seed_summary") or "").strip()
    mood = str(meta.get("mood") or "").strip()
    genre = str(meta.get("style") or "").strip()
    wf = ensure_workflow(doc)
    skip_lyrics = bool(wf.get("skip_lyrics"))

    sections = ordered_sections(doc)
    h_done, h_total = harmonized_section_count(doc)
    m_done, m_total = melodized_section_count(doc)
    l_done, l_total = lyrics_section_count(doc)

    empty_harmony = [str(s.get("label_variant") or s.get("label")) for s in sections if not section_has_chords(s)]
    empty_melody = [str(s.get("label_variant") or s.get("label")) for s in sections if not section_has_melody(s)]
    empty_lyrics: list[str] = []
    if not skip_lyrics:
        empty_lyrics = [
            str(s.get("label_variant") or s.get("label")) for s in sections if not section_has_lyrics(s)
        ]

    themes = collect_song_lyric_themes(doc)
    counts = _count_sections_by_label(doc)
    verses = counts.get("Verse", 0)
    choruses = counts.get("Chorus", 0)

    parts: list[str] = [
        "<strong>Listening to your song as a whole</strong> — here's what stands out.",
    ]

    if idea:
        parts.append(
            f'Your vision started with: <em>"{idea[:160]}{"…" if len(idea) > 160 else ""}"</em>. '
            f"{'That intent still reads clearly in the form you built.' if sections else 'Shape the structure so the idea has room to land.'}"
        )
    if genre or mood:
        bits = " · ".join(x for x in (genre, mood) if x)
        parts.append(f"Tone on the page: <strong>{bits}</strong>.")

    strengths: list[str] = []
    if h_total and h_done == h_total:
        strengths.append("harmony across every section")
    elif h_done > 0:
        strengths.append("a harmonic foundation to build on")
    if m_total and m_done == m_total:
        strengths.append("melodic ideas in each section")
    elif m_done > 0:
        strengths.append("melodic direction in key spots")
    if skip_lyrics:
        strengths.append("a focused instrumental arc")
    elif l_total and l_done == l_total:
        strengths.append("lyrics written throughout the form")
    elif l_done > 0:
        strengths.append("lyrical threads started")
    if themes:
        strengths.append("recurring themes and images")
    if strengths:
        parts.append(f"<strong>Strengths:</strong> {', '.join(strengths)}.")

    if themes and not skip_lyrics:
        joined = "; ".join(themes[:4])
        parts.append(
            f"<strong>Consistency:</strong> {joined}. "
            "When you polish, echo those images in sections that still feel thin."
        )

    if verses or choruses:
        balance = f"{verses} verse{'s' if verses != 1 else ''}, {choruses} chorus{'es' if choruses != 1 else ''}"
        if choruses == 0 and verses > 0:
            parts.append(
                f"Form balance: {balance} — consider whether a chorus (or hook section) would anchor the song."
            )
        elif verses == 0 and choruses > 0:
            parts.append(f"Form balance: {balance} — verses often carry the story before the chorus lifts.")
        else:
            parts.append(f"Form balance: {balance} — check that energy rises where listeners expect the hook.")

    gaps: list[str] = []
    if empty_harmony:
        gaps.append(f"chords still open on {', '.join(empty_harmony[:4])}")
    if empty_melody:
        gaps.append(f"melody still open on {', '.join(empty_melody[:4])}")
    if empty_lyrics:
        gaps.append(f"lyrics still open on {', '.join(empty_lyrics[:4])}")
    if gaps:
        parts.append(f"<strong>Still developing:</strong> {'; '.join(gaps)}.")

    if song_is_ready(doc):
        parts.append(
            "<strong>Ready?</strong> The core phases look complete — play the full song below, "
            "then refine anything that doesn't feel true to your vision."
        )
    else:
        parts.append(
            "<strong>Ready?</strong> Not quite yet — use the checklist and jump back to any phase "
            "until the whole song feels like one piece."
        )

    return "<br><br>".join(parts)
