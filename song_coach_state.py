"""Song-Aware Coaching (S3) — the coaching session a musician is working through.

One small, JSON-ready record under :data:`SONG_COACH_STATE_KEY` holds *choices and progress
only*: which song it belongs to, the draft selection (section, bars, level, focus), the inputs
of the built plan and its id, the current challenge and the ticked self-checks.

- **The plan itself is never stored.** Plans are deterministic, so the plan is rebuilt from
  the stored inputs and must reproduce the stored ``plan_id``; anything else is discarded.
- **Belongs to one song.** A record whose ``identity`` is not the live song's is ignored
  (never shown, never adopted). A record for the same song whose chart or concert Practice
  Key changed keeps the musician's choices but its plan is invalidated.
- **Instrument changes are not invalidation.** Plans are concert pitch; Written / Shape
  names are projected at display time.
- **Reads never write.** :func:`reconcile` is read-only; every write comes from a user action
  (a widget callback) through :func:`commit`, which follows the Creative context user-event
  save path (canonical commit → workspace dirty → explicit save), like Harmony Map selections.
- **No global writes.** Practice Focus, Practice Key, instrument, level and Backing settings
  are read, never written.
- **Examples (S4)** are stored as *which challenges show one* plus the musician's "new idea"
  counter; the phrases are regenerated deterministically from the plan id, so they keep their
  identity across reruns, navigation, refreshes and instrument changes, and are cleared with
  the plan whenever the song, Practice Key or chart changes.
- **Damaged records recover (S6).** A saved record is read field by field: a field that
  can't be read (wrong type, unknown level or focus, out-of-range tempo …) falls back to its
  default and the musician is told part of the session was reset; an unreadable record, or one
  saved by a newer version, starts fresh with a clear message. Nothing is ever trusted just
  because it was saved — the plan is always rebuilt and its id verified.
- **Practice loop (S5)** settings are the musician's tempo (0 = the song's tempo) and whether
  the loop follows the challenge's bars or the whole selection. They are preferences, kept
  across plan rebuilds; the loop audio itself is identified by its own signature (song, chart,
  key, bars, tempo, style), so stale audio is never reused.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Mapping

SONG_COACH_STATE_KEY = "song_coach_session"
PLAN_CACHE_KEY = "_song_coach_plan_cache"  # session-only: {plan_id: CoachingPlan}
EXAMPLE_CACHE_KEY = "_song_coach_example_cache"  # session-only: {plan_id|nonce|stage|instrument: Example}
LAST_COMMIT_KEY = "_song_coach_last_commit"  # session-only diagnostic: which user action last saved
STATE_VERSION = 1
LOOP_RANGE_CHALLENGE = "challenge"
LOOP_RANGE_SELECTION = "selection"
LOOP_RANGES = (LOOP_RANGE_CHALLENGE, LOOP_RANGE_SELECTION)
SAVE_REASON = "song_coach_session_change"

NOTICE_OTHER_SONG = "other_song"
NOTICE_CHART_CHANGED = "chart_changed"
NOTICE_PLAN_STALE = "plan_stale"
NOTICE_STATE_UNREADABLE = "state_unreadable"
NOTICE_STATE_REPAIRED = "state_repaired"
NOTICE_STATE_NEWER = "state_newer"
NOTICE_MESSAGES = {
    NOTICE_OTHER_SONG: "Your earlier coaching plan was for a different song, so you're starting fresh here.",
    NOTICE_CHART_CHANGED: "The Practice Key or the chord chart changed since you built your plan. Build it again to coach in the new key.",
    NOTICE_PLAN_STALE: "Your saved plan no longer matches this song's chart, so it was cleared. Build a new one when you're ready.",
    NOTICE_STATE_UNREADABLE: "Your saved coaching session couldn't be read, so coaching starts fresh. Choose your bars and build a new plan.",
    NOTICE_STATE_REPAIRED: "Part of your saved coaching session couldn't be read and was reset to its default.",
    NOTICE_STATE_NEWER: "Your saved coaching session comes from a newer version of the app, so coaching starts fresh here.",
}
STATUS_OK = ""
STATUS_UNREADABLE = "unreadable"
STATUS_REPAIRED = "repaired"
STATUS_NEWER = "newer"


@dataclass(frozen=True)
class Selection:
    section_id: str = ""
    start_bar: int = 0
    end_bar: int = 0
    level: str = ""
    focus: str = ""

    @property
    def complete(self) -> bool:
        return bool(self.section_id and self.start_bar and self.end_bar and self.level and self.focus)


@dataclass(frozen=True)
class CoachState:
    identity: str = ""
    fingerprint: str = ""
    draft: Selection = field(default_factory=Selection)
    built: Selection = field(default_factory=Selection)
    plan_id: str = ""
    instrument: str = ""  # instrument the plan was built for (its id includes the family)
    stage: int = 0
    checks: dict[str, tuple[int, ...]] = field(default_factory=dict)
    examples: tuple[int, ...] = ()  # challenges whose example is shown (hidden until asked)
    example_nonce: int = 0  # "try a different example idea" counter (part of the example seed)
    loop_bpm: int = 0  # practice-loop tempo; 0 = the song's own tempo
    loop_range: str = LOOP_RANGE_CHALLENGE  # loop the challenge's bars or the whole selection
    version: int = STATE_VERSION

    @property
    def has_plan(self) -> bool:
        return bool(self.plan_id and self.built.complete)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["checks"] = {k: list(v) for k, v in self.checks.items()}
        d["examples"] = list(self.examples)
        return d

    @classmethod
    def from_dict(cls, raw: Any) -> "CoachState | None":
        """The record, or ``None`` when it can't be read at all (see :func:`parse_state`)."""
        state, status = parse_state(raw)
        return state if status in (STATUS_OK, STATUS_REPAIRED) else None


def _int(value: Any, default: int, problems: list[str], name: str, *, lo: int | None = None, hi: int | None = None) -> int:
    if value is None or value == "":
        return default
    try:
        out = int(value)
        if isinstance(value, bool) or (isinstance(value, float) and not value.is_integer()):
            raise ValueError(value)
    except (TypeError, ValueError, OverflowError):
        problems.append(name)
        return default
    if (lo is not None and out < lo) or (hi is not None and out > hi):
        problems.append(name)
        return default
    return out


def _str(value: Any, problems: list[str], name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        problems.append(name)
        return ""
    return value


def _selection(raw: Any, problems: list[str], name: str) -> Selection:
    from song_coach_plan import FOCUSES, LEVELS

    if raw is None:
        return Selection()
    if not isinstance(raw, Mapping):
        problems.append(name)
        return Selection()
    level = _str(raw.get("level"), problems, f"{name}.level")
    focus = _str(raw.get("focus"), problems, f"{name}.focus")
    if level and level not in LEVELS:
        problems.append(f"{name}.level")
        level = ""
    if focus and focus not in FOCUSES:
        problems.append(f"{name}.focus")
        focus = ""
    sel = Selection(
        _str(raw.get("section_id"), problems, f"{name}.section_id"),
        _int(raw.get("start_bar"), 0, problems, f"{name}.start_bar", lo=0),
        _int(raw.get("end_bar"), 0, problems, f"{name}.end_bar", lo=0),
        level, focus,
    )
    if sel.start_bar and sel.end_bar and sel.end_bar < sel.start_bar:
        problems.append(f"{name}.bars")
        return Selection(level=level, focus=focus)
    return sel


def parse_state(raw: Any) -> tuple[CoachState | None, str]:
    """Read a saved record field by field: ``(state, status)``.

    ``status`` is ``""`` (clean), ``"repaired"`` (some fields fell back to defaults — the rest
    of the record is kept), ``"unreadable"`` (not a record at all) or ``"newer"`` (saved by a
    newer record version, which this build must not guess at)."""
    from song_coach_backing import TEMPO_MAX, TEMPO_MIN

    if raw is None:
        return None, STATUS_OK
    if not isinstance(raw, Mapping):
        return None, STATUS_UNREADABLE
    problems: list[str] = []
    version = _int(raw.get("version"), STATE_VERSION, problems, "version", lo=1)
    if version > STATE_VERSION:
        return None, STATUS_NEWER
    checks: dict[str, tuple[int, ...]] = {}
    raw_checks = raw.get("checks")
    if isinstance(raw_checks, Mapping):
        for k, v in raw_checks.items():
            stage_key = _int(k, -1, problems, "checks", lo=0)
            if stage_key < 0 or not isinstance(v, (list, tuple)):
                if stage_key >= 0:
                    problems.append("checks")
                continue
            items = {_int(i, -1, problems, "checks", lo=0) for i in v}
            checks[str(stage_key)] = tuple(sorted(i for i in items if i >= 0))
    elif raw_checks is not None:
        problems.append("checks")
    examples: set[int] = set()
    raw_examples = raw.get("examples")
    if isinstance(raw_examples, (list, tuple)):
        examples = {_int(i, -1, problems, "examples", lo=0) for i in raw_examples}
        examples.discard(-1)
    elif raw_examples is not None:
        problems.append("examples")
    loop_bpm = _int(raw.get("loop_bpm"), 0, problems, "loop_bpm", lo=0)
    if loop_bpm and not TEMPO_MIN <= loop_bpm <= TEMPO_MAX:
        problems.append("loop_bpm")
        loop_bpm = 0
    loop_range = _str(raw.get("loop_range"), problems, "loop_range") or LOOP_RANGE_CHALLENGE
    if loop_range not in LOOP_RANGES:
        problems.append("loop_range")
        loop_range = LOOP_RANGE_CHALLENGE
    state = CoachState(
        identity=_str(raw.get("identity"), problems, "identity"),
        fingerprint=_str(raw.get("fingerprint"), problems, "fingerprint"),
        draft=_selection(raw.get("draft"), problems, "draft"),
        built=_selection(raw.get("built"), problems, "built"),
        plan_id=_str(raw.get("plan_id"), problems, "plan_id"),
        instrument=_str(raw.get("instrument"), problems, "instrument"),
        stage=_int(raw.get("stage"), 0, problems, "stage", lo=0),
        checks=checks,
        examples=tuple(sorted(examples)),
        example_nonce=_int(raw.get("example_nonce"), 0, problems, "example_nonce", lo=0),
        loop_bpm=loop_bpm,
        loop_range=loop_range,
        version=STATE_VERSION,
    )
    if not state.identity:  # a record that belongs to no song: damaged unless it is simply empty
        return None, STATUS_UNREADABLE if (problems or len(raw)) else STATUS_OK
    return state, STATUS_REPAIRED if problems else STATUS_OK


@dataclass(frozen=True)
class Reconciled:
    """What the UI shows this run (computed read-only from the stored record)."""

    state: CoachState
    plan: Any = None  # CoachingPlan
    scope: Any = None  # CoachScope of the plan
    notice: str = ""


def read_state(session: Mapping[str, Any]) -> CoachState | None:
    return parse_state(session.get(SONG_COACH_STATE_KEY))[0]


# --------------------------------------------------------------------------- defaults


def default_selection(ctx: Any, *, level: str, focus: str) -> Selection:
    """First musical section (skip Intro / Outro when there is a choice), its first phrase."""
    from song_coach_plan import normalize_focus, normalize_level
    from song_coach_scope import coach_sections, suggested_ranges

    sections = coach_sections(ctx)
    if not sections:
        return Selection(level=normalize_level(level), focus=normalize_focus(focus))
    body = [s for s in sections if s.label.lower() not in ("intro", "outro")] or sections
    sec = body[0]
    start, end = suggested_ranges(sec)[0]
    return Selection(sec.section_id, start, end, normalize_level(level), normalize_focus(focus))


def valid_selection(ctx: Any, sel: Selection) -> bool:
    from song_coach_scope import MAX_SCOPE_BARS, find_section

    sec = find_section(ctx, sel.section_id) if sel.section_id else None
    return bool(
        sec is not None
        and 1 <= sel.start_bar <= sel.end_bar <= sec.bar_count
        and sel.end_bar - sel.start_bar + 1 <= MAX_SCOPE_BARS
    )


# --------------------------------------------------------------------------- reconcile (read-only)


def _plan_cache(session: Any) -> dict[str, Any]:
    cache = session.get(PLAN_CACHE_KEY) if hasattr(session, "get") else None
    return cache if isinstance(cache, dict) else {}


def build_plan_for(ctx: Any, sel: Selection, *, instrument: str = "") -> tuple[Any, Any]:
    from song_coach_plan import build_coaching_plan
    from song_coach_scope import build_scope

    scope = build_scope(ctx, sel.section_id, sel.start_bar, sel.end_bar)
    plan = build_coaching_plan(ctx, scope, level=sel.level, focus=sel.focus, instrument=instrument or ctx.instrument)
    return plan, scope


def _cleared(state: CoachState, **changes: Any) -> CoachState:
    """The plan and everything that belongs to it (progress, checks, examples) removed."""
    return replace(state, built=Selection(), plan_id="", stage=0, checks={}, examples=(), example_nonce=0, **changes)


def reconcile(session: Mapping[str, Any], ctx: Any, *, level: str, focus: str) -> Reconciled:
    """The coaching view for the live song — never another song's plan, never a write."""
    fresh = CoachState(identity=ctx.identity, fingerprint=ctx.fingerprint, draft=default_selection(ctx, level=level, focus=focus))
    stored, status = parse_state(session.get(SONG_COACH_STATE_KEY) if hasattr(session, "get") else None)
    if stored is None:
        notice = {STATUS_UNREADABLE: NOTICE_STATE_UNREADABLE, STATUS_NEWER: NOTICE_STATE_NEWER}.get(status, "")
        return Reconciled(fresh, notice=notice)
    if stored.identity != ctx.identity:
        return Reconciled(fresh, notice=NOTICE_OTHER_SONG)
    rec = _reconcile_same_song(session, ctx, stored, fresh)
    if status == STATUS_REPAIRED and not rec.notice:
        return replace(rec, notice=NOTICE_STATE_REPAIRED)
    return rec


def _reconcile_same_song(session: Mapping[str, Any], ctx: Any, stored: CoachState, fresh: CoachState) -> Reconciled:
    draft = stored.draft if valid_selection(ctx, stored.draft) and stored.draft.complete else fresh.draft
    if stored.fingerprint != ctx.fingerprint:
        cleared = _cleared(stored, fingerprint=ctx.fingerprint, draft=draft)
        return Reconciled(cleared, notice=NOTICE_CHART_CHANGED if stored.has_plan else "")
    state = replace(stored, draft=draft)
    if not stored.has_plan:
        return Reconciled(state)
    if not valid_selection(ctx, stored.built):
        return Reconciled(_cleared(state), notice=NOTICE_PLAN_STALE)
    from song_coach_plan import plan_id_for

    try:
        live_key = _cache_key(stored, ctx)
        cached = _plan_cache(session).get(live_key)
        plan, scope = cached if cached is not None else build_plan_for(ctx, stored.built)
    except Exception:  # an unbuildable plan is cleared, never shown half-made
        return Reconciled(_cleared(state), notice=NOTICE_PLAN_STALE)
    # The stored id must be reproduced for the instrument the plan was built for; the plan
    # shown uses the live instrument (only its instrument tip differs, never the challenges).
    expected = plan_id_for(scope.scope_id, plan.level, plan.focus, plan.style, stored.instrument)
    if expected != stored.plan_id or plan.context_fingerprint != ctx.fingerprint:
        return Reconciled(_cleared(state), notice=NOTICE_PLAN_STALE)
    stage = min(stored.stage, len(plan.challenges) - 1)
    examples = tuple(i for i in stored.examples if i < len(plan.challenges))
    return Reconciled(replace(state, stage=stage, examples=examples), plan=plan, scope=scope)


def _cache_key(state: CoachState, ctx: Any) -> str:
    return f"{state.plan_id}|{ctx.projection_fingerprint}"


def cache_plan(session: Any, state: CoachState, ctx: Any, plan: Any, scope: Any) -> None:
    """Session-only plan cache (not persisted): keeps reruns fast; rebuilt after a refresh."""
    session[PLAN_CACHE_KEY] = {_cache_key(state, ctx): (plan, scope)}


# --------------------------------------------------------------------------- user actions (write)


def commit(session: Any, state: CoachState, *, interaction: str) -> None:
    """Store a user change and save it through the Creative context user-event path."""
    value = state.to_dict()
    session[LAST_COMMIT_KEY] = {"interaction": interaction, "run_seq": session.get("_script_run_seq")}
    try:
        from creative_context_snapshot_persistence import (
            SAVE_REASON_CONTEXT_SNAPSHOT,
            _context_slice,
            _record_user_event,
            commit_context_snapshot_to_canonical,
            request_context_cloud_save,
        )
    except ImportError:
        session[SONG_COACH_STATE_KEY] = value
        return
    _record_user_event(
        session, interaction=f"song_coach:{interaction}", save_reason=SAVE_REASON_CONTEXT_SNAPSHOT,
        fields={SONG_COACH_STATE_KEY: value},
    )
    session[SONG_COACH_STATE_KEY] = copy.deepcopy(value)
    commit_context_snapshot_to_canonical(
        session, reason=SAVE_REASON_CONTEXT_SNAPSHOT, values={**_context_slice(session), SONG_COACH_STATE_KEY: value}
    )
    try:
        from creative_workspace_persistence import mark_creative_workspace_dirty

        mark_creative_workspace_dirty(session)
    except ImportError:
        pass
    request_context_cloud_save(session, save_reason=SAVE_REASON_CONTEXT_SNAPSHOT)


def with_draft(state: CoachState, **changes: Any) -> CoachState:
    return replace(state, draft=replace(state.draft, **changes))


def with_built_plan(state: CoachState, plan: Any) -> CoachState:
    return replace(state, built=state.draft, plan_id=plan.plan_id, instrument=plan.instrument, stage=0, checks={},
                   examples=(), example_nonce=0)


def with_example(state: CoachState, stage: int, shown: bool) -> CoachState:
    current = set(state.examples)
    current.add(int(stage)) if shown else current.discard(int(stage))
    return replace(state, examples=tuple(sorted(current)))


def with_loop(state: CoachState, *, bpm: int | None = None, loop_range: str | None = None) -> CoachState:
    """Practice-loop preferences (tempo 0 = the song's tempo)."""
    changes: dict[str, Any] = {}
    if bpm is not None:
        changes["loop_bpm"] = max(0, int(bpm))
    if loop_range is not None and loop_range in LOOP_RANGES:
        changes["loop_range"] = loop_range
    return replace(state, **changes)


def with_new_example_idea(state: CoachState) -> CoachState:
    """A different seed idea: every example of the plan changes together (they share the seed)."""
    return replace(state, example_nonce=state.example_nonce + 1)


def example_for(session: Any, state: CoachState, plan: Any, scope: Any, stage: int) -> Any:
    """The example for ``stage`` — generated from the *stored* plan id and the instrument the
    plan was built for, so it is the same phrase on every rerun and after an instrument change
    (only its written / shape display changes). Cached for this session only."""
    from song_coach_examples import build_example

    key = f"{state.plan_id}|{state.example_nonce}|{int(stage)}|{state.instrument}"
    cache = session.get(EXAMPLE_CACHE_KEY) if hasattr(session, "get") else None
    cache = cache if isinstance(cache, dict) and cache.get("plan_id") == state.plan_id else {"plan_id": state.plan_id}
    if key not in cache:
        cache[key] = build_example(plan, scope, int(stage), nonce=state.example_nonce, instrument=state.instrument,
                                   plan_key=state.plan_id)
        session[EXAMPLE_CACHE_KEY] = cache
    return cache[key]


def with_stage(state: CoachState, stage: int, total: int) -> CoachState:
    return replace(state, stage=max(0, min(int(stage), max(0, total - 1))))


def with_check(state: CoachState, stage: int, item: int, ticked: bool) -> CoachState:
    key = str(stage)
    current = set(state.checks.get(key, ()))
    current.add(item) if ticked else current.discard(item)
    checks = dict(state.checks)
    checks[key] = tuple(sorted(current))
    return replace(state, checks=checks)


def done_stages(state: CoachState, plan: Any) -> set[int]:
    """A challenge is done once every self-check item is ticked."""
    out = set()
    for i, ch in enumerate(plan.challenges):
        need = set(range(len(ch.checklist)))
        if need and need <= set(state.checks.get(str(i), ())):
            out.add(i)
    return out


__all__ = [
    "CoachState",
    "EXAMPLE_CACHE_KEY",
    "LOOP_RANGES",
    "LOOP_RANGE_CHALLENGE",
    "LOOP_RANGE_SELECTION",
    "NOTICE_CHART_CHANGED",
    "NOTICE_MESSAGES",
    "NOTICE_OTHER_SONG",
    "NOTICE_PLAN_STALE",
    "NOTICE_STATE_NEWER",
    "NOTICE_STATE_REPAIRED",
    "NOTICE_STATE_UNREADABLE",
    "PLAN_CACHE_KEY",
    "Reconciled",
    "SONG_COACH_STATE_KEY",
    "STATE_VERSION",
    "Selection",
    "build_plan_for",
    "cache_plan",
    "commit",
    "default_selection",
    "done_stages",
    "parse_state",
    "example_for",
    "read_state",
    "reconcile",
    "valid_selection",
    "with_built_plan",
    "with_check",
    "with_draft",
    "with_example",
    "with_loop",
    "with_new_example_idea",
    "with_stage",
]
