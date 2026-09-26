"""Slice 4 — explicit Backing owner envelopes.

Every Backing launch seals who opened it and which musical inputs belonged to
that launch. Post-navigation code must not re-guess Catalog / SBI / Jam /
Mission / Composition from unrelated global leftovers.

Semantic key fields stay separate (Slice 3 lesson):
  Original ≠ Practice/Concert ≠ Sounding ≠ Written ≠ Shape

Canonical logical owners (no duplicate aliases after handoff normalization):
  catalog | sbi_custom | entry_jam | mission | composition
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

# Session persistence key — survives refresh / reboot with backing_context.
BACKING_OWNER_ENVELOPE_KEY = "_backing_owner_envelope"

# Canonical owners
OWNER_CATALOG = "catalog"
OWNER_SBI_CUSTOM = "sbi_custom"
OWNER_ENTRY_JAM = "entry_jam"
OWNER_MISSION = "mission"
OWNER_COMPOSITION = "composition"

CANONICAL_OWNERS = frozenset(
    {
        OWNER_CATALOG,
        OWNER_SBI_CUSTOM,
        OWNER_ENTRY_JAM,
        OWNER_MISSION,
        OWNER_COMPOSITION,
    }
)

# Compatibility tokens seen on older handoffs / BackingContext.source.
# Normalized once at the handoff boundary — never stored as envelope.source.
_ALIAS_TO_OWNER: dict[str, str] = {
    "catalog": OWNER_CATALOG,
    "regular_song": OWNER_CATALOG,
    "regular_catalog_backing": OWNER_CATALOG,
    "sbi_custom": OWNER_SBI_CUSTOM,
    "custom": OWNER_SBI_CUSTOM,
    "custom_progression": OWNER_SBI_CUSTOM,
    "song_improv": OWNER_SBI_CUSTOM,  # refined below when Active song ≠ Custom
    "entry_jam": OWNER_ENTRY_JAM,
    "style_jam": OWNER_ENTRY_JAM,
    "jam_generator": OWNER_ENTRY_JAM,
    "jam_session_generator": OWNER_ENTRY_JAM,
    "mission": OWNER_MISSION,
    "mission_jam": OWNER_MISSION,
    "composition": OWNER_COMPOSITION,
    "composition_song": OWNER_COMPOSITION,
}

# Return destinations derived solely from envelope owner.
RETURN_BY_OWNER: dict[str, str] = {
    OWNER_CATALOG: "catalog",
    OWNER_SBI_CUSTOM: "sbi_custom",
    OWNER_ENTRY_JAM: "entry_jam",
    OWNER_MISSION: "mission",
    OWNER_COMPOSITION: "composition",
}

# Map envelope owner → legacy BackingContext.source token.
CTX_SOURCE_BY_OWNER: dict[str, str] = {
    OWNER_CATALOG: "regular_song",
    OWNER_SBI_CUSTOM: "song_improv",
    OWNER_ENTRY_JAM: "entry_jam",
    OWNER_MISSION: "mission",
    OWNER_COMPOSITION: "composition_song",
}


def _tok(value: Any) -> str:
    return str(value or "").strip()


def _session_map(session: Any) -> Any:
    if session is None:
        return {}
    if isinstance(session, Mapping):
        return session
    if hasattr(session, "get") and hasattr(session, "__setitem__"):
        return session
    return {}


@dataclass
class BackingOwnerEnvelope:
    """Authoritative launch snapshot for one Backing visit."""

    source: str
    identity: str = ""
    title: str = ""
    original_key: str = ""
    practice_key: str = ""
    sounding_key: str = ""
    written_key: str = ""
    shape_key: str = ""
    capo: int | str = ""
    instrument: str = ""
    progression: list[str] = field(default_factory=list)
    progression_label: str = ""
    style: str = ""
    tempo: int | str = ""
    meter: str = ""
    return_destination: str = ""
    # Optional subtype for entry_jam (Style Jam vs Generator) — same owner.
    entry_mode: str = ""
    # Epoch bumps on every explicit launch; PK mutations keep the same epoch.
    epoch: int = 0

    def as_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["progression"] = list(self.progression or [])
        return raw

    def coherent_tuple(self) -> tuple[str, str, str, str, str, str, tuple[str, ...], str]:
        """owner / identity / original / practice / sounding / display-space / progression / return."""
        display_space = self.written_key or self.shape_key or self.sounding_key or self.practice_key
        return (
            self.source,
            self.identity,
            self.original_key,
            self.practice_key,
            self.sounding_key or self.practice_key,
            display_space,
            tuple(self.progression or ()),
            self.return_destination or RETURN_BY_OWNER.get(self.source, ""),
        )


def normalize_backing_owner(
    raw: str,
    *,
    session: Mapping[str, Any] | None = None,
    sbi_preview: str = "",
) -> str:
    """Map legacy / ambiguous tokens to one canonical owner at the handoff boundary."""
    token = _tok(raw).lower()
    if not token:
        return ""
    if token in CANONICAL_OWNERS:
        return token
    # song_improv is ambiguous: Custom tab → sbi_custom; Active catalog → catalog.
    if token in {"song_improv", "sbi", "sbi_active"}:
        preview = _tok(sbi_preview)
        if not preview and session is not None:
            try:
                from source_session_state import get_sbi_preview_source

                preview = _tok(get_sbi_preview_source(session))
            except Exception:
                preview = _tok(session.get("sbi_preview_source") or session.get("improv_song_source") or "")
        if preview.lower() in {"custom progression", "custom"}:
            return OWNER_SBI_CUSTOM
        # Nested Custom SBI overlay also means Trial Custom, not Catalog.
        if session is not None and (
            session.get("_nested_custom_sbi_backing")
            or session.get("_sbi_custom_sidebar_overlay")
        ):
            return OWNER_SBI_CUSTOM
        # Active song SBI: catalog identity owns the musical material.
        return OWNER_CATALOG
    mapped = _ALIAS_TO_OWNER.get(token, "")
    if mapped == OWNER_SBI_CUSTOM and token == "song_improv":
        return normalize_backing_owner("song_improv", session=session, sbi_preview=sbi_preview)
    return mapped


def clear_backing_owner_envelope(session: dict[str, Any]) -> None:
    ss = _session_map(session)
    try:
        ss.pop(BACKING_OWNER_ENVELOPE_KEY, None)
    except Exception:
        pass


def get_backing_owner_envelope(session: dict[str, Any] | None) -> BackingOwnerEnvelope | None:
    ss = _session_map(session)
    raw = ss.get(BACKING_OWNER_ENVELOPE_KEY)
    if not isinstance(raw, dict):
        return None
    source = normalize_backing_owner(_tok(raw.get("source") or ""), session=ss)
    if source not in CANONICAL_OWNERS:
        return None
    progression = raw.get("progression") or []
    if not isinstance(progression, list):
        progression = list(progression) if progression else []
    return BackingOwnerEnvelope(
        source=source,
        identity=_tok(raw.get("identity") or ""),
        title=_tok(raw.get("title") or ""),
        original_key=_tok(raw.get("original_key") or ""),
        practice_key=_tok(raw.get("practice_key") or ""),
        sounding_key=_tok(raw.get("sounding_key") or ""),
        written_key=_tok(raw.get("written_key") or ""),
        shape_key=_tok(raw.get("shape_key") or ""),
        capo=raw.get("capo") if raw.get("capo") not in (None, "") else "",
        instrument=_tok(raw.get("instrument") or ""),
        progression=[_tok(c) for c in progression if _tok(c)],
        progression_label=_tok(raw.get("progression_label") or ""),
        style=_tok(raw.get("style") or ""),
        tempo=raw.get("tempo") if raw.get("tempo") not in (None, "") else "",
        meter=_tok(raw.get("meter") or ""),
        return_destination=_tok(raw.get("return_destination") or "")
        or RETURN_BY_OWNER.get(source, ""),
        entry_mode=_tok(raw.get("entry_mode") or ""),
        epoch=int(raw.get("epoch") or 0),
    )


def live_backing_owner(session: dict[str, Any] | None) -> str:
    """Authoritative owner while on Backing — envelope first, never global leftovers."""
    env = get_backing_owner_envelope(session)
    if env is not None and env.source in CANONICAL_OWNERS:
        return env.source
    return ""


def stamp_backing_owner_envelope(
    session: dict[str, Any],
    *,
    source: str,
    identity: str = "",
    title: str = "",
    original_key: str = "",
    practice_key: str = "",
    sounding_key: str = "",
    written_key: str = "",
    shape_key: str = "",
    capo: Any = "",
    instrument: str = "",
    progression: list[str] | tuple[str, ...] | None = None,
    progression_label: str = "",
    style: str = "",
    tempo: Any = "",
    meter: str = "",
    return_destination: str = "",
    entry_mode: str = "",
    bump_epoch: bool = True,
) -> BackingOwnerEnvelope:
    """Seal an explicit Backing launch. Overwrites any prior owner envelope."""
    ss = _session_map(session)
    owner = normalize_backing_owner(source, session=ss)
    if owner not in CANONICAL_OWNERS:
        raise ValueError(f"backing_owner_envelope: unknown source {source!r}")

    prev = get_backing_owner_envelope(ss)
    epoch = int(prev.epoch if prev is not None else 0)
    if bump_epoch:
        epoch += 1

    practice = _tok(practice_key)
    sounding = _tok(sounding_key) or practice
    # Never let written/shape pollute Practice or sounding.
    if written_key and _tok(written_key) == practice and practice:
        # Keep as-is when they truly match (concert instrument).
        written = _tok(written_key)
    else:
        written = _tok(written_key)

    env = BackingOwnerEnvelope(
        source=owner,
        identity=_tok(identity),
        title=_tok(title),
        original_key=_tok(original_key),
        practice_key=practice,
        sounding_key=sounding,
        written_key=written,
        shape_key=_tok(shape_key),
        capo=capo if capo not in (None, "") else "",
        instrument=_tok(instrument) or _tok(ss.get("instrument") or ""),
        progression=[_tok(c) for c in (progression or []) if _tok(c)],
        progression_label=_tok(progression_label),
        style=_tok(style),
        tempo=tempo if tempo not in (None, "") else "",
        meter=_tok(meter),
        return_destination=_tok(return_destination) or RETURN_BY_OWNER[owner],
        entry_mode=_tok(entry_mode),
        epoch=epoch,
    )
    ss[BACKING_OWNER_ENVELOPE_KEY] = env.as_dict()

    # Keep legacy handoff token aligned (compatibility boundary).
    try:
        from creative_source_ownership_contract import stamp_explicit_backing_handoff

        legacy = CTX_SOURCE_BY_OWNER.get(owner, owner)
        existing_handoff = _tok(ss.get("_backing_explicit_handoff_source") or "")
        # Custom page still uses custom_progression on BackingContext.
        if owner == OWNER_SBI_CUSTOM:
            preview = ""
            try:
                from source_session_state import get_sbi_preview_source

                preview = _tok(get_sbi_preview_source(ss))
            except Exception:
                preview = _tok(ss.get("sbi_preview_source") or "")
            page = _tok(ss.get("studio_page") or "").lower()
            if (
                page == "custom"
                or _tok(ss.get("_backing_entry_class") or "") == "custom"
                or existing_handoff == "custom_progression"
            ):
                legacy = "custom_progression"
            else:
                legacy = "song_improv"
        elif owner == OWNER_CATALOG and existing_handoff == "song_improv":
            # Active-song SBI launch: musical owner is catalog, Creative return stays SBI.
            legacy = "song_improv"
            if not env.return_destination or env.return_destination == OWNER_CATALOG:
                env.return_destination = "creative"
                ss[BACKING_OWNER_ENVELOPE_KEY] = env.as_dict()
        stamp_explicit_backing_handoff(ss, legacy)
    except Exception:
        ss["_backing_explicit_handoff_source"] = CTX_SOURCE_BY_OWNER.get(owner, owner)
        ss["_backing_explicit_handoff_epoch"] = epoch

    ss["_backing_pk_control_owner"] = owner
    ss.pop("_backing_released_specialized_context", None)
    return env


def update_envelope_musical_state(
    session: dict[str, Any],
    *,
    practice_key: str = "",
    sounding_key: str = "",
    written_key: str = "",
    shape_key: str = "",
    capo: Any = None,
    progression: list[str] | tuple[str, ...] | None = None,
    tempo: Any = None,
    style: str = "",
    meter: str = "",
    instrument: str = "",
) -> BackingOwnerEnvelope | None:
    """Mutate musical fields only — never change source / identity / return."""
    env = get_backing_owner_envelope(session)
    if env is None:
        return None
    if practice_key:
        env.practice_key = _tok(practice_key)
        env.sounding_key = _tok(sounding_key) or env.practice_key
    elif sounding_key:
        env.sounding_key = _tok(sounding_key)
    if written_key:
        env.written_key = _tok(written_key)
    if shape_key:
        env.shape_key = _tok(shape_key)
    if capo is not None:
        env.capo = capo if capo not in (None, "") else ""
    if progression is not None:
        env.progression = [_tok(c) for c in progression if _tok(c)]
    if tempo is not None and tempo != "":
        env.tempo = tempo
    if style:
        env.style = _tok(style)
    if meter:
        env.meter = _tok(meter)
    if instrument:
        env.instrument = _tok(instrument)
    _session_map(session)[BACKING_OWNER_ENVELOPE_KEY] = env.as_dict()
    return env


def stamp_envelope_from_backing_context(
    session: dict[str, Any],
    ctx: Any,
    *,
    source_override: str = "",
    return_destination: str = "",
    written_key: str = "",
    shape_key: str = "",
    capo: Any = "",
) -> BackingOwnerEnvelope | None:
    """Seal envelope from a freshly built BackingContext at launch."""
    if ctx is None:
        return None
    raw_source = _tok(source_override) or _tok(getattr(ctx, "source", "") or "")
    owner = normalize_backing_owner(raw_source, session=session)
    if owner not in CANONICAL_OWNERS:
        return None

    identity = _tok(
        getattr(ctx, "bound_pick_key", "")
        or getattr(ctx, "active_song_id", "")
        or getattr(ctx, "custom_revision_id", "")
        or ""
    )
    title = _tok(getattr(ctx, "song_title", "") or getattr(ctx, "progression_label", "") or "")
    original = _tok(getattr(ctx, "key", "") or "")
    practice = _tok(getattr(ctx, "concert_key", "") or getattr(ctx, "display_key", "") or "")
    progression = list(getattr(ctx, "progression", None) or [])
    entry_mode = _tok(getattr(ctx, "entry_mode", "") or "")

    # Prefer Mission-sealed concert fields when present.
    if owner == OWNER_MISSION:
        try:
            from mission_owner_contract import (
                HANDOFF_ORIGINAL_KEY,
                HANDOFF_PRACTICE_KEY,
                HANDOFF_SOUNDING_KEY,
                HANDOFF_WRITTEN_KEY,
            )

            original = _tok(session.get(HANDOFF_ORIGINAL_KEY) or "") or original
            practice = _tok(session.get(HANDOFF_PRACTICE_KEY) or "") or practice
            sounding = _tok(session.get(HANDOFF_SOUNDING_KEY) or "") or practice
            written = _tok(written_key) or _tok(session.get(HANDOFF_WRITTEN_KEY) or "")
        except ImportError:
            sounding = practice
            written = _tok(written_key)
    else:
        sounding = practice
        written = _tok(written_key)

    if not shape_key:
        try:
            from guitar_capo import CAPO_SHAPE_KEY

            shape_key = _tok(session.get(CAPO_SHAPE_KEY) or "")
        except ImportError:
            shape_key = _tok(session.get("guitar_capo_shape_key") or "")
    if capo in (None, ""):
        try:
            from guitar_capo import CAPO_FRET_KEY

            capo = session.get(CAPO_FRET_KEY)
        except ImportError:
            capo = session.get("guitar_capo_fret") or session.get("capo") or ""

    return stamp_backing_owner_envelope(
        session,
        source=owner,
        identity=identity,
        title=title,
        original_key=original,
        practice_key=practice,
        sounding_key=sounding if owner == OWNER_MISSION else practice,
        written_key=written,
        shape_key=_tok(shape_key),
        capo=capo if capo not in (None, "") else "",
        instrument=_tok(getattr(ctx, "instrument", "") or session.get("instrument") or ""),
        progression=progression,
        progression_label=_tok(getattr(ctx, "progression_label", "") or title),
        style=_tok(getattr(ctx, "style", "") or getattr(ctx, "groove", "") or ""),
        tempo=getattr(ctx, "bpm", "") or "",
        meter=_tok(getattr(ctx, "meter", "") or session.get("improv_style_meter") or ""),
        return_destination=_tok(return_destination) or RETURN_BY_OWNER[owner],
        entry_mode=entry_mode,
        bump_epoch=True,
    )


def ensure_envelope_matches_backing_context(
    session: dict[str, Any],
    ctx: Any,
    *,
    source_override: str = "",
    return_destination: str = "",
    written_key: str = "",
) -> BackingOwnerEnvelope | None:
    """Stamp a new envelope epoch only when live owner disagrees with ctx.

    Used when Backing UI adopts Catalog/Custom/Composition context without going
    through ``open_backing_for_practice_source`` (card/reconcile paths). Does not
    bump epoch when the envelope already matches — avoids rerun thrash.
    """
    if ctx is None:
        return get_backing_owner_envelope(session)
    raw_source = _tok(source_override) or _tok(getattr(ctx, "source", "") or "")
    owner = normalize_backing_owner(raw_source, session=session)
    if owner not in CANONICAL_OWNERS:
        return get_backing_owner_envelope(session)
    if live_backing_owner(session) == owner:
        return get_backing_owner_envelope(session)
    return stamp_envelope_from_backing_context(
        session,
        ctx,
        source_override=owner,
        return_destination=return_destination or RETURN_BY_OWNER[owner],
        written_key=written_key,
    )


def envelope_return_destination(session: dict[str, Any] | None) -> str:
    env = get_backing_owner_envelope(session)
    if env is None:
        return ""
    return env.return_destination or RETURN_BY_OWNER.get(env.source, "")


def envelope_allows_return(session: dict[str, Any] | None, destination: str) -> bool:
    """True only when the envelope owner matches the requested return family."""
    want = _tok(destination).lower()
    got = envelope_return_destination(session).lower()
    if not want or not got:
        return False
    if want == got:
        return True
    # Aliases for UI action ids.
    aliases = {
        "mission": {OWNER_MISSION, "return_mission"},
        "sbi_custom": {OWNER_SBI_CUSTOM, "creative", "return_creative"},
        "entry_jam": {OWNER_ENTRY_JAM, "creative", "return_creative"},
        "composition": {OWNER_COMPOSITION, "return_composition"},
        "catalog": {OWNER_CATALOG, "songs", "return_catalog"},
    }
    allowed = aliases.get(got, {got})
    return want in allowed or want == got


def assert_envelope_coherent(session: dict[str, Any] | None) -> tuple[str, ...]:
    """Return human-readable violations if envelope fields disagree internally."""
    env = get_backing_owner_envelope(session)
    if env is None:
        return ("missing_envelope",)
    violations: list[str] = []
    if env.source not in CANONICAL_OWNERS:
        violations.append(f"bad_source:{env.source}")
    if not env.identity and env.source != OWNER_ENTRY_JAM:
        # Jam may use ephemeral identity; others should seal one.
        if env.source in {OWNER_CATALOG, OWNER_COMPOSITION, OWNER_SBI_CUSTOM, OWNER_MISSION}:
            violations.append("missing_identity")
    if env.practice_key and env.sounding_key and env.practice_key != env.sounding_key:
        # Sounding must track Practice/Concert — written/shape are separate.
        violations.append(
            f"practice_sounding_mismatch:{env.practice_key}/{env.sounding_key}"
        )
    if env.written_key and env.practice_key and env.written_key == env.practice_key:
        # Not always a violation (concert instruments). Leave as soft.
        pass
    if env.return_destination and env.return_destination != RETURN_BY_OWNER.get(env.source, ""):
        # Custom return ok if still same family; flag hard mismatches.
        if env.source == OWNER_MISSION and env.return_destination != OWNER_MISSION:
            violations.append(f"return_mismatch:{env.return_destination}")
        if env.source == OWNER_COMPOSITION and env.return_destination != OWNER_COMPOSITION:
            violations.append(f"return_mismatch:{env.return_destination}")
    return tuple(violations)


__all__ = [
    "BACKING_OWNER_ENVELOPE_KEY",
    "OWNER_CATALOG",
    "OWNER_SBI_CUSTOM",
    "OWNER_ENTRY_JAM",
    "OWNER_MISSION",
    "OWNER_COMPOSITION",
    "CANONICAL_OWNERS",
    "RETURN_BY_OWNER",
    "CTX_SOURCE_BY_OWNER",
    "BackingOwnerEnvelope",
    "normalize_backing_owner",
    "clear_backing_owner_envelope",
    "get_backing_owner_envelope",
    "live_backing_owner",
    "stamp_backing_owner_envelope",
    "update_envelope_musical_state",
    "stamp_envelope_from_backing_context",
    "ensure_envelope_matches_backing_context",
    "envelope_return_destination",
    "envelope_allows_return",
    "assert_envelope_coherent",
]
