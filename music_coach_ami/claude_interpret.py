"""AMI M1b-4 (experimental, developer-only, OFF by default): let Claude *interpret* a request that the fixed rules cannot parse.

Claude never writes music. It receives a compact, sanitized description of the working exercise and the player's sentence, and answers with a
structured interpretation drawn from a **closed vocabulary** of operations the deterministic engines already perform
("shape fourths", "approach both", "sync_less", "instrument alto", "section Section B", "explain guide_tones", ...). That proposal is then
validated deterministically — known operation, allowed argument, no conflicting pair, the player's "keep ..." constraints respected, instrument
supported, section really on the chart — and only then handed to the existing engines (``exercise_scale_pattern.revise``, ``exercise_adapt``,
``exercise_explain``), which produce, verify and version the actual notes. Anything unsupported, ambiguous or invalid is rejected, never guessed;
the deterministic answer (the unchanged exercise and an honest "I can't do that yet") is the fallback whenever the API is off, unavailable,
over budget or wrong.

Gates (all must hold, otherwise nothing is sent): ``AMI_CLAUDE_ENABLED`` and ``AMI_CLAUDE_INTERPRET_ENABLED`` are true, the session is in developer
mode, the developer toggle is on, and the model is priced. The same fail-closed budget ledger as the coaching enrichment records every request.
The model sees no notes, no chord symbols, no lyrics and no account data: only the recipe fields, instrument, section *names* and the sentence.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from music_coach_ami.claude_client import AnthropicTransport, ClaudeTransport, TransportError
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

CACHE_KEY = "_ami_claude_interpret_cache"
LAST_KEY = "_ami_claude_interpret_last"
SESSION_ID_KEY = "_ami_claude_sid"

# The closed vocabulary. (operation -> allowed arguments; an empty tuple means "no argument".)
OPS: dict[str, tuple[str, ...]] = {
    "shape": ("scalar", "thirds", "fourths", "fifths", "mixed"),
    "interval_advance": (), "wider": (), "narrower": (), "simplify_notes": (),
    "approach": ("below", "above", "both"), "approach_more": (), "approach_off": (),
    "anticipate": ("on", "off"), "displace": ("on", "off"),
    "sync_more": (), "sync_less": (), "new_rhythm": (),
    "harder": (), "easier": (),
    "instrument": ("flute", "piano", "alto", "tenor", "soprano", "baritone", "trumpet", "clarinet"),
    "section": (),            # the argument is a section name; validated against the chart
    "explain": ("why_notes", "chord_tones", "guide_tones", "approaches", "intervals", "improvising", "last_change"),
}
PITCH_OPS = {"shape", "interval_advance", "wider", "narrower", "simplify_notes", "approach", "approach_more", "approach_off"}
RHYTHM_OPS = {"displace", "sync_more", "sync_less", "new_rhythm"}
PATTERN_OPS = PITCH_OPS | RHYTHM_OPS | {"anticipate", "harder", "easier"}
CONFLICTS = (("approach", "approach_off"), ("approach_more", "approach_off"), ("sync_more", "sync_less"), ("harder", "easier"),
             ("wider", "narrower"), ("interval_advance", "simplify_notes"), ("shape", "interval_advance"))
KEEP = ("rhythm", "notes", "instrument", "section", "tempo")
CLARIFY = ("", "which_change", "which_instrument", "which_section", "not_about_the_exercise", "unsupported_request")
CLARIFY_TEXT = {
    "which_change": "I'm not sure which change you mean. Could you say it a little more specifically — for example “change it to fourths”, “add chromatic approaches”, "
                    "“make the rhythm straighter” or “make it more advanced”?",
    "which_instrument": "Which instrument should I adapt it for? I can do flute, piano, soprano / alto / tenor / baritone saxophone, trumpet and clarinet.",
    "which_section": "Which section of the song should I apply it to?",
    "unsupported_request": "That's not something I can do to an existing exercise yet, so I haven't changed anything.",
}

INTERPRETATION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "operations": {"type": "array", "items": {
            "type": "object",
            "properties": {"op": {"type": "string", "enum": list(OPS)}, "arg": {"type": "string"}},
            "required": ["op", "arg"], "additionalProperties": False}},
        "keep": {"type": "array", "items": {"type": "string", "enum": list(KEEP)}},
        "clarify": {"type": "string", "enum": list(CLARIFY)},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["operations", "keep", "clarify", "confidence"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You translate a musician's sentence about the practice exercise on their screen into a structured request for AMI's music engines.
You do NOT write or choose any notes, chords, scales or pitches. You only choose from the allowed operations below.

Allowed operations (op: allowed arg):
- shape: scalar | thirds | fourths | fifths | mixed          (the interval pattern)
- interval_advance, wider, narrower, simplify_notes          (arg ""): more varied / wider / narrower / simpler intervals
- approach: below | above | both ; approach_more ; approach_off   (chromatic approach notes)
- anticipate: on | off ; displace: on | off                   (harmonic anticipation; rhythmic displacement)
- sync_more, sync_less, new_rhythm                            (arg ""): rhythm only
- harder, easier                                              (arg ""): overall difficulty
- instrument: flute | piano | alto | tenor | soprano | baritone | trumpet | clarinet   (adapt the same exercise to another instrument)
- section: the exact section name, chosen ONLY from available_sections   (rebuild the same pattern on that section's chords)
- explain: why_notes | chord_tones | guide_tones | approaches | intervals | improvising | last_change   (an explanation; changes nothing)

Rules:
- Use the fewest operations that satisfy the sentence (at most 3). Never combine explain, instrument or section with other operations.
- "keep": list what the musician said to keep unchanged, from rhythm | notes | instrument | section | tempo. Never choose an operation that changes something in "keep".
- If the sentence is vague, e.g. "smoother" with no clear meaning, "more useful" with no clear meaning, or you cannot choose confidently, return no operations and set clarify.
- clarify values: which_change | which_instrument | which_section | not_about_the_exercise | unsupported_request | "" (empty when you chose operations).
- Never invent an instrument or section. If a named instrument or section is not allowed or not available, return no operations and set clarify to unsupported_request.
- arg must be "" when the operation takes no argument.
Respond with JSON only."""


@dataclass(frozen=True)
class Interpretation:
    ok: bool
    ops: tuple[tuple[str, str], ...] = ()
    keep: tuple[str, ...] = ()
    clarify: str = ""
    reason: str = ""                       # why a proposal was rejected (diagnostics; never shown as a musical claim)
    confidence: str = ""
    kind: str = ""                         # "pattern" | "instrument" | "section" | "explain" | ""


def interpretation_gate(settings: ClaudeSettings, session_state: Any) -> tuple[bool, str]:
    if not settings.master_enabled:
        return False, "disabled_by_config"
    if not settings.interpret_enabled:
        return False, "interpret_disabled"
    if session_state.get("_ami_claude_dev_mode") is not True:
        return False, "not_developer_mode"
    if session_state.get("_ami_claude_dev_enabled") is not True:
        return False, "dev_toggle_off"
    if not settings.model_priced:
        return False, "unpriced_model"
    return True, "enabled"


# ---------------------------------------------------------------- what is sent (sanitized, compact)


def build_context(exercise: dict[str, Any], question: str, available_sections: list[str], recent_labels: list[str]) -> dict[str, Any]:
    prov = exercise.get("provenance") or {}
    recipe = dict(prov.get("recipe") or {})
    return {
        "request": " ".join(str(question or "").split())[:300],
        "exercise": {
            "kind": prov.get("kind"), "instrument": (exercise.get("context") or {}).get("instrument"), "bars": exercise.get("bars"),
            "section": (exercise.get("context") or {}).get("section"), "recipe": recipe,
        },
        "available_sections": [str(s)[:40] for s in available_sections][:24],
        "recent_requests": [" ".join(str(x).split())[:120] for x in recent_labels][-3:],
    }


def _fingerprint(ctx: dict[str, Any], model: str) -> str:
    return hashlib.sha1((model + json.dumps(ctx, sort_keys=True, default=str)).encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- deterministic validation of the proposal


def parse_payload_text(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raise ValueError("code fence")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("not an object")
    return data


def validate(payload: dict[str, Any], *, sections: list[str], is_chord_following: bool) -> Interpretation:
    """Accept only a proposal made entirely of known operations with allowed arguments that respects every "keep" and every engine limit."""
    if set(payload) - {"operations", "keep", "clarify", "confidence"}:
        return Interpretation(False, reason="unexpected_fields")
    ops_raw, keep_raw = payload.get("operations"), payload.get("keep")
    clarify, confidence = payload.get("clarify", ""), str(payload.get("confidence") or "")
    if not isinstance(ops_raw, list) or not isinstance(keep_raw, list) or clarify not in CLARIFY:
        return Interpretation(False, reason="bad_shape")
    keep = tuple(k for k in keep_raw if k in KEEP)
    if len(keep) != len(keep_raw):
        return Interpretation(False, reason="unknown_keep")
    if not ops_raw:
        return Interpretation(True, ops=(), keep=keep, clarify=clarify or "which_change", confidence=confidence)
    if clarify:
        return Interpretation(False, reason="operations_and_clarify")
    if len(ops_raw) > 3:
        return Interpretation(False, reason="too_many_operations")
    ops: list[tuple[str, str]] = []
    for item in ops_raw:
        if not isinstance(item, dict) or set(item) != {"op", "arg"} or not isinstance(item["op"], str) or not isinstance(item["arg"], str):
            return Interpretation(False, reason="bad_operation")
        name, arg = item["op"], item["arg"].strip()
        if name not in OPS:
            return Interpretation(False, reason=f"unknown_operation:{name[:20]}")
        if name == "section":
            if arg not in sections:
                return Interpretation(False, reason="unknown_section")
        elif OPS[name]:
            if arg not in OPS[name]:
                return Interpretation(False, reason=f"bad_argument:{name}")
        elif arg:
            return Interpretation(False, reason=f"unexpected_argument:{name}")
        ops.append((name, arg))
    names = [n for n, _a in ops]
    if len(set(ops)) != len(ops):
        return Interpretation(False, reason="duplicate_operation")
    for a, b in CONFLICTS:
        if a in names and b in names:
            return Interpretation(False, reason=f"conflict:{a}+{b}")
    if ("anticipate", "on") in ops and ("anticipate", "off") in ops or ("displace", "on") in ops and ("displace", "off") in ops:
        return Interpretation(False, reason="conflict:on+off")
    single = [n for n in names if n in {"instrument", "section", "explain"}]
    if single and len(ops) > 1:
        return Interpretation(False, reason="mixed_kinds")
    if "rhythm" in keep and any(n in RHYTHM_OPS or n in {"harder", "easier"} for n in names):
        return Interpretation(False, reason="violates_keep_rhythm")
    if "notes" in keep and any(n in PITCH_OPS or n in {"harder", "easier", "instrument", "section"} for n in names):
        return Interpretation(False, reason="violates_keep_notes")
    if "instrument" in keep and "instrument" in names:
        return Interpretation(False, reason="violates_keep_instrument")
    if "section" in keep and "section" in names:
        return Interpretation(False, reason="violates_keep_section")
    if not is_chord_following and ("section" in names or ("anticipate", "on") in ops):
        return Interpretation(False, reason="needs_chord_following")
    kind = "instrument" if "instrument" in names else "section" if "section" in names else "explain" if "explain" in names else "pattern"
    return Interpretation(True, ops=tuple(ops), keep=keep, clarify="", confidence=confidence, kind=kind)


def describe(interp: Interpretation) -> str:
    """The operations in the player's words, shown so they can see how their sentence was read."""
    words = {
        "shape": lambda a: {"scalar": "scale steps"}.get(a, a), "interval_advance": lambda a: "more varied intervals", "wider": lambda a: "wider intervals",
        "narrower": lambda a: "narrower intervals", "simplify_notes": lambda a: "simpler notes", "approach": lambda a: f"chromatic approaches ({a})",
        "approach_more": lambda a: "more chromatic approaches", "approach_off": lambda a: "no chromatic approaches", "anticipate": lambda a: f"anticipations {a}",
        "displace": lambda a: f"displacement {a}", "sync_more": lambda a: "more syncopation", "sync_less": lambda a: "straighter rhythm",
        "new_rhythm": lambda a: "a new rhythm on the same notes", "harder": lambda a: "harder", "easier": lambda a: "easier",
        "instrument": lambda a: f"for {a}", "section": lambda a: f"over {a}", "explain": lambda a: f"explain {a.replace('_', ' ')}",
    }
    return ", ".join(words[n](a) for n, a in interp.ops)


# ---------------------------------------------------------------- the call


def interpret(
    question: str,
    exercise: dict[str, Any],
    session_state: Any,
    *,
    sections: list[str],
    recent_labels: list[str],
    transport_factory: Callable[[str], ClaudeTransport] | None = None,
    settings: ClaudeSettings | None = None,
) -> tuple[Interpretation | None, dict[str, Any]]:
    """(interpretation or ``None`` when nothing was asked of Claude / the call failed, a diagnostics record). Never raises."""
    try:
        return _interpret(question, exercise, session_state, sections, recent_labels, transport_factory, settings)
    except Exception as exc:  # noqa: BLE001 - the deterministic path must never be broken by the experiment
        return None, {"status": "internal_error", "error_type": type(exc).__name__}


def _interpret(question, exercise, session_state, sections, recent_labels, transport_factory, settings):
    cfg = settings or load_claude_settings()
    ok, reason = interpretation_gate(cfg, session_state)
    if not ok:
        return None, {"status": "skipped", "reason": reason}
    ctx = build_context(exercise, question, sections, recent_labels)
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
    user_prompt = "EXERCISE AND REQUEST (JSON):\n" + json.dumps(ctx, sort_keys=True, ensure_ascii=False) + "\n\nReturn the structured interpretation as JSON."
    max_out = min(cfg.max_output_tokens, 400)
    worst = estimate_worst_case_micro_usd(cfg.model, prompt_chars=len(SYSTEM_PROMPT) + len(user_prompt), max_output_tokens=max_out)
    try:
        reservation = reserve_budget(cfg, session_id=sid, fingerprint=fingerprint, intent="interpret", model=cfg.model, worst_case_micro_usd=worst)
    except BudgetRefused as exc:
        return None, {**base, "status": "refused", "reason": exc.reason}
    except LedgerError as exc:
        return None, {**base, "status": "refused", "reason": f"ledger_unavailable:{exc}"}
    degraded = False
    try:
        result = transport.complete(model=cfg.model, system=SYSTEM_PROMPT, user=user_prompt, schema=INTERPRETATION_JSON_SCHEMA,
                                    max_output_tokens=max_out, effort=cfg.effort, timeout_s=cfg.timeout_s)
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
    interp: Interpretation | None = None
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
            chord_following = (exercise.get("provenance") or {}).get("kind") == "chord_following"
            checked = validate(payload, sections=sections, is_chord_following=chord_following)
            if checked.ok:
                status, interp = "accepted", checked
            else:
                status, violations = "rejected", (checked.reason,)
    try:
        settle(reservation, model=cfg.model, usage=usage, request_id=result.request_id, status=status, violations=violations, force_cost_micro_usd=forced)
    except (LedgerError, ValueError):
        degraded = True
    record = {**base, "status": status, "violations": list(violations), "request_id": result.request_id, "stop_reason": result.stop_reason,
              "usage": {k: int(v) for k, v in usage.items()}, "cost_usd": micro_to_usd(cost), "ledger_degraded": degraded}
    cache[fingerprint] = {"record": record, "interpretation": interp}
    return interp, record
