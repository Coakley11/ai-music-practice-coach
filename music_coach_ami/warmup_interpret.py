"""AMI adaptive warmups, Slice 1 (experimental, developer-only, OFF by default, NOT wired into the live path): let Claude *plan* from a sentence.

The deterministic parser (``warmup_plan.parse_request``) reads what it can. Some sentences carry more than it understands — "something to get my
embouchure and my fingers ready for a gig, short on long tones" — and that is where Claude can help: it turns the sentence into a structured
*plan request* drawn from a **closed vocabulary** (families, excluded families, interval names, articulation patterns, minutes, level, focus).
It never writes notes, keys, chords or tempos. Its answer is validated deterministically — known names, no family both wanted and excluded, a
length inside 2-30 minutes — and only then handed to ``warmup_plan.create`` (``request=``), whose engines build, verify and time the actual exercises.
Anything unsupported or invalid is rejected, never guessed; the rules' own reading is the fallback whenever the API is off, unavailable, over
budget or wrong.

Gates (all must hold, otherwise nothing is sent) are the same as the exercise interpretation layer's: ``AMI_CLAUDE_ENABLED`` and
``AMI_CLAUDE_INTERPRET_ENABLED``, developer mode, the developer toggle, a priced model, a key, and the fail-closed budget ledger. The model sees
the sentence and the player's level, and nothing else: no notes, no song, no account data.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from music_coach_ami import warmup_engine as we
from music_coach_ami.claude_client import AnthropicTransport, ClaudeTransport, TransportError
from music_coach_ami.claude_interpret import interpretation_gate, parse_payload_text
from music_coach_ami.claude_settings import ClaudeSettings, load_claude_settings
from music_coach_ami.claude_usage import (
    BudgetRefused,
    LedgerError,
    compute_cost_micro_usd,
    estimate_worst_case_micro_usd,
    micro_to_usd,
    new_session_id,
    release,
    reserve_budget,
    settle,
)

CACHE_KEY = "_ami_claude_warmup_cache"
LAST_KEY = "_ami_claude_warmup_last"
SESSION_ID_KEY = "_ami_claude_sid"

FOCUS = ("", "tone", "technique", "articulation", "speed")
CLARIFY = ("", "which_instrument", "not_a_warmup", "unsupported_request")

WARMUP_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "families": {"type": "array", "items": {"type": "string", "enum": list(we.FAMILIES)}},
        "excluded": {"type": "array", "items": {"type": "string", "enum": list(we.FAMILIES)}},
        "intervals": {"type": "array", "items": {"type": "string", "enum": list(we.INTERVALS)}},
        "articulation": {"type": "array", "items": {"type": "string", "enum": list(we.ARTIC_PATTERNS)}},
        "minutes": {"type": "number"},
        "level": {"type": "string", "enum": ["", *we.LEVELS]},
        "emphasis": {"type": "array", "items": {"type": "string", "enum": list(we.FAMILIES)}},
        "focus": {"type": "string", "enum": list(FOCUS)},
        "clarify": {"type": "string", "enum": list(CLARIFY)},
    },
    "required": ["families", "excluded", "intervals", "articulation", "minutes", "level", "emphasis", "focus", "clarify"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You translate a musician's sentence asking for a practice warmup into a structured request for AMI's music engines.
You do NOT write or choose any notes, keys, chords, tempos or exercises. You only choose from the allowed values below.

Fields:
- families: what the musician asked to include, from long_tones | scale | intervals | articulation. Empty when they named none (AMI then chooses a balanced mix).
- excluded: families they asked to leave out ("no long tones", "skip scales").
- intervals: only when intervals are wanted: seconds | thirds | fourths | fifths | sixths | sevenths | octaves.
- articulation: only when articulation is wanted: repeated (tonguing one note) | two_note (two-note slurs and tongued pairs) | slur_tongue (slur two, tongue two) | contrast (legato / staccato / accent / tenuto).
- minutes: the length they asked for, 2 to 30. Use 0 when they did not say.
- level: Beginner | Intermediate | Advanced, or "" when they did not say.
- emphasis: families they want more time on ("heavy on articulation", "mostly scales").
- focus: tone | technique | articulation | speed, or "" when no single aim is clear.
- clarify: which_instrument (they did not say which instrument and it matters) | not_a_warmup (the sentence is not asking for a warmup) | unsupported_request (it asks for something AMI cannot build, such as a warmup for a specific song's chords, jazz vocabulary, or an instrument other than flute, piano, saxophone, trumpet or clarinet) | "".

Rules:
- Never put a family in both families and excluded.
- Choose only what the sentence says or clearly implies; do not add things to be helpful.
- If the sentence asks for something outside the allowed values, return the parts you can and set clarify to unsupported_request.
- "fingers", "finger technique" and "dexterity" mean technique; "tone", "sound", "breath" and "embouchure" mean tone; "tonguing" and "slurs" mean articulation.
Respond with JSON only."""


@dataclass(frozen=True)
class WarmupInterpretation:
    ok: bool
    request: dict[str, Any] | None = None       # the fields ``warmup_plan.create`` reads from a parsed request
    clarify: str = ""
    reason: str = ""


def _as_list(value: Any) -> list[str] | None:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        return None
    return [x.strip() for x in value]


def validate(payload: dict[str, Any]) -> WarmupInterpretation:
    """Accept only a closed-vocabulary plan request. Everything else is rejected with a reason (never repaired by guessing)."""
    if not isinstance(payload, dict):
        return WarmupInterpretation(False, reason="not_an_object")
    extra = set(payload) - set(WARMUP_JSON_SCHEMA["properties"])
    if extra:
        return WarmupInterpretation(False, reason=f"unknown_fields:{sorted(extra)}")
    fams, excl, ivs, arts, emph = (_as_list(payload.get(k)) for k in ("families", "excluded", "intervals", "articulation", "emphasis"))
    if None in (fams, excl, ivs, arts, emph):
        return WarmupInterpretation(False, reason="bad_list")
    for name, values, allowed in (("families", fams, we.FAMILIES), ("excluded", excl, we.FAMILIES), ("emphasis", emph, we.FAMILIES),
                                  ("intervals", ivs, tuple(we.INTERVALS)), ("articulation", arts, we.ARTIC_PATTERNS)):
        bad = [v for v in values if v not in allowed]
        if bad:
            return WarmupInterpretation(False, reason=f"unknown_{name}:{bad}")
        if len(set(values)) != len(values):
            return WarmupInterpretation(False, reason=f"duplicate_{name}")
    if set(fams) & set(excl):
        return WarmupInterpretation(False, reason="family_both_included_and_excluded")
    if set(emph) & set(excl):
        return WarmupInterpretation(False, reason="emphasis_on_an_excluded_family")
    if ivs and fams and "intervals" not in fams:
        return WarmupInterpretation(False, reason="intervals_without_the_intervals_family")
    if arts and fams and "articulation" not in fams:
        return WarmupInterpretation(False, reason="articulation_patterns_without_the_articulation_family")
    minutes = payload.get("minutes", 0)
    if isinstance(minutes, bool) or not isinstance(minutes, (int, float)):
        return WarmupInterpretation(False, reason="bad_minutes")
    if minutes and not (2 <= float(minutes) <= 30):
        return WarmupInterpretation(False, reason="minutes_out_of_range")
    level = payload.get("level", "")
    if level not in ("", *we.LEVELS):
        return WarmupInterpretation(False, reason="unknown_level")
    focus = payload.get("focus", "")
    if focus not in FOCUS:
        return WarmupInterpretation(False, reason="unknown_focus")
    clarify = payload.get("clarify", "")
    if clarify not in CLARIFY:
        return WarmupInterpretation(False, reason="unknown_clarify")
    if clarify in ("which_instrument", "not_a_warmup"):
        return WarmupInterpretation(False, clarify=clarify, reason=clarify)
    request = {"families": list(fams), "excluded": list(excl), "intervals": list(ivs), "artic": list(arts), "minutes": float(minutes) if minutes else None,
               "level": level, "focus": focus, "emphasis": list(emph)}
    if len(set(fams) | set(excl)) == 0 and not minutes and not level and not focus and not ivs and not arts and clarify == "unsupported_request":
        return WarmupInterpretation(False, clarify=clarify, reason="nothing_usable")
    return WarmupInterpretation(True, request=request, clarify=clarify)


def merge_into(parsed: dict[str, Any], interp: WarmupInterpretation) -> dict[str, Any]:
    """The rules win wherever they found something explicit; Claude only fills in what the rules left empty."""
    if not interp.ok or interp.request is None:
        return parsed
    r = interp.request
    out = dict(parsed)
    if not parsed.get("families"):
        out["families"] = [f for f in r["families"] if f not in (parsed.get("excluded") or [])]
    out["excluded"] = list(dict.fromkeys([*(parsed.get("excluded") or []), *r["excluded"]]))
    out["families"] = [f for f in out["families"] if f not in out["excluded"]]
    if not parsed.get("intervals"):
        out["intervals"] = list(r["intervals"])
    if not parsed.get("artic"):
        out["artic"] = list(r["artic"])
    if parsed.get("minutes") is None and r["minutes"]:
        out["minutes"] = r["minutes"]
    if not parsed.get("level") and r["level"]:
        out["level"] = r["level"]
    if not parsed.get("focus") and r["focus"]:
        out["focus"] = r["focus"]
    out["more"] = {f: 1.6 for f in r["emphasis"] if f not in out["excluded"]}
    out["interpreted_by_claude"] = True
    return out


def build_context(question: str, level: str) -> dict[str, Any]:
    return {"sentence": " ".join(str(question or "").split())[:400], "level_on_the_page": level if level in we.LEVELS else ""}


def _fingerprint(ctx: dict[str, Any], model: str) -> str:
    return hashlib.sha1(json.dumps([ctx, model, "warmup-v1"], sort_keys=True).encode("utf-8")).hexdigest()[:16]


def interpret(question: str, level: str, session_state: Any, *, transport_factory: Callable[[str], ClaudeTransport] | None = None,
              settings: ClaudeSettings | None = None) -> tuple[WarmupInterpretation | None, dict[str, Any]]:
    """(interpretation or ``None`` when nothing was asked of Claude / the call failed, a diagnostics record). Never raises."""
    try:
        return _interpret(question, level, session_state, transport_factory, settings)
    except Exception as exc:  # noqa: BLE001 - the deterministic path must never be broken by the experiment
        return None, {"status": "internal_error", "error_type": type(exc).__name__}


def _interpret(question, level, session_state, transport_factory, settings):
    cfg = settings or load_claude_settings()
    ok, reason = interpretation_gate(cfg, session_state)
    if not ok:
        return None, {"status": "skipped", "reason": reason}
    ctx = build_context(question, level)
    fingerprint = _fingerprint(ctx, cfg.model)
    cache = session_state.get(CACHE_KEY)
    if not isinstance(cache, dict):
        cache = {}
        session_state[CACHE_KEY] = cache
    if fingerprint in cache:
        entry = cache[fingerprint]
        return entry["interpretation"], {**entry["record"], "cache_hit": True, "cost_usd": 0.0}
    from anthropic_secrets_config import resolve_anthropic_api_key

    api_key, _probe = resolve_anthropic_api_key()
    base: dict[str, Any] = {"model": cfg.model, "fingerprint": fingerprint, "cache_hit": False}
    if not api_key:
        return None, {**base, "status": "skipped", "reason": "no_api_key"}
    try:
        transport = (transport_factory or AnthropicTransport)(api_key)
    except TransportError as exc:
        return None, {**base, "status": "skipped", "reason": exc.kind}
    sid = session_state.get(SESSION_ID_KEY)
    if not sid:
        sid = new_session_id()
        session_state[SESSION_ID_KEY] = sid
    user_prompt = "REQUEST (JSON):\n" + json.dumps(ctx, sort_keys=True, ensure_ascii=False) + "\n\nReturn the structured plan request as JSON."
    max_out = min(cfg.max_output_tokens, 300)
    worst = estimate_worst_case_micro_usd(cfg.model, prompt_chars=len(SYSTEM_PROMPT) + len(user_prompt), max_output_tokens=max_out)
    try:
        reservation = reserve_budget(cfg, session_id=sid, fingerprint=fingerprint, intent="warmup_plan", model=cfg.model, worst_case_micro_usd=worst)
    except BudgetRefused as exc:
        return None, {**base, "status": "refused", "reason": exc.reason}
    except LedgerError as exc:
        return None, {**base, "status": "refused", "reason": f"ledger_unavailable:{exc}"}
    degraded = False
    try:
        result = transport.complete(model=cfg.model, system=SYSTEM_PROMPT, user=user_prompt, schema=WARMUP_JSON_SCHEMA, max_output_tokens=max_out,
                                    effort=cfg.effort, timeout_s=cfg.timeout_s)
    except TransportError as exc:
        status, cost = f"api_error:{exc.kind}", 0
        try:
            if exc.billed == "no":
                release(reservation, status=status, error_type=exc.error_type)
            else:
                cost = settle(reservation, model=cfg.model, usage={}, request_id="", status=f"billing_unknown:{exc.kind}",
                              force_cost_micro_usd=reservation.worst_case_micro_usd)
        except LedgerError:
            degraded = True
        return None, {**base, "status": status, "error_type": exc.error_type, "cost_usd": micro_to_usd(cost), "ledger_degraded": degraded}
    usage = dict(result.usage)
    forced: int | None = None
    try:
        cost = compute_cost_micro_usd(cfg.model, usage)
    except (ValueError, LedgerError):
        cost = reservation.worst_case_micro_usd
        forced = cost
    interp: WarmupInterpretation | None = None
    violations: tuple[str, ...] = ()
    if result.stop_reason == "refusal":
        status = "refusal"
    elif result.stop_reason != "end_turn":
        status = f"incomplete:{result.stop_reason or 'unknown'}"
    else:
        try:
            payload = parse_payload_text(result.text)
        except ValueError:
            status = "invalid_json"
        else:
            checked = validate(payload)
            if checked.ok:
                status, interp = "accepted", checked
            else:
                status, violations, interp = "rejected", (checked.reason,), checked
    try:
        settle(reservation, model=cfg.model, usage=usage, request_id=result.request_id, status=status, violations=violations, force_cost_micro_usd=forced)
    except (LedgerError, ValueError):
        degraded = True
    record = {**base, "status": status, "violations": list(violations), "request_id": result.request_id, "stop_reason": result.stop_reason,
              "usage": {k: int(v) for k, v in usage.items()}, "cost_usd": micro_to_usd(cost), "ledger_degraded": degraded}
    cache[fingerprint] = {"record": record, "interpretation": interp}
    return interp, record
