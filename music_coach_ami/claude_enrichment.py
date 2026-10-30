"""Optional Claude coaching enrichment for song-coaching answers. Never raises; the deterministic answer is never altered."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from music_coach_ami.claude_client import AnthropicTransport, ClaudeTransport, TransportError
from music_coach_ami.claude_facts import FactSheet, build_fact_sheet
from music_coach_ami.claude_settings import ClaudeSettings, enrichment_gate, load_claude_settings
from music_coach_ami.claude_usage import (
    BudgetRefused,
    LedgerError,
    Reservation,
    compute_cost_micro_usd,
    estimate_worst_case_micro_usd,
    micro_to_usd,
    new_session_id,
    release,
    reserve_budget,
    settle,
)
from music_coach_ami.claude_validate import ENRICHMENT_JSON_SCHEMA, parse_payload_text, validate_enrichment
from music_coach_ami.types import CoachRequest, CoachResponse

CACHE_KEY = "_ami_claude_cache"
SESSION_ID_KEY = "_ami_claude_sid"
LAST_KEY = "_ami_claude_last"

SYSTEM_PROMPT = """You add a short supplementary coaching note to a practice answer that has already been verified.

You receive FACTS taken from the musician's active song chart, and the EXISTING ANSWER already shown to them.
The FACTS are the only musical facts you may use.

Hard rules:
- Never state, imply or invent any chord, key, section, tempo, pitch or note name that is not in FACTS. Never transpose or respell a chord.
- Mark every concrete musical token you mention exactly like this: {{chord:Dm7}}, {{key:F}}, {{section:Verse}}, {{bpm:90}}. Use the value exactly as it appears in FACTS (BPM values from the EXISTING ANSWER are also allowed).
- Do not name individual pitches or notes. Do not name scales or modes. Do not claim anything about the original recording, melody, lyrics, modulations or bar numbers.
- Focus on how to practice: listening focus, chord-change preparation, rhythm and tempo strategy, looping, and what to check.
- FACTS names are CONCERT pitch. Never mention written pitch, transposition, octaves, capos or how an instrument reads or sounds; the app adds any written-pitch label itself. Keys you mark are shown labelled "concert" for transposing instruments.
- Add to the EXISTING ANSWER; do not repeat it or contradict it.
- Follow FACTS.coaching_brief: build the guidance around its primary_angle and secondary_angle, work in at most two instrument_cues naturally in your own words, and match level_scope (item count and style). Do not copy the brief's wording.
- Tempo: mention a BPM or tempo target only if coaching_brief.may_mention_tempo is true. Recording or playback advice only if coaching_brief.may_suggest_recording is true. Otherwise leave both out entirely.
- Avoid stock phrasing such as "name the next chord aloud", "last beat", or "in small steps" unless the brief's angle is exactly that; each note should read differently for different exercises, instruments and levels.
- Use American English spelling (for example "practice" for the verb, "color", "center").
- Plain text only: no markdown, no lists inside items, no links.
- why_this_fits: one or two sentences, at most 320 characters.
- guidance: 2 to 4 items, each at most 260 characters.
- listen_for: 0 to 3 items, each at most 200 characters.
Respond with JSON only."""


def _build_user_prompt(facts: FactSheet) -> str:
    return (
        "FACTS (verified from the active song chart):\n"
        f"{facts.facts_json()}\n\n"
        "EXISTING ANSWER (already shown to the musician):\n"
        f"{facts.existing_answer}\n\n"
        "Write the supplementary coaching note as JSON."
    )


def _record(
    resp: CoachResponse,
    session_state: Any,
    record: dict[str, Any],
    *,
    diagnostics: bool = True,
) -> None:
    if diagnostics:
        diag = dict(resp.diagnostics or {})
        diag["ai_enrichment"] = record
        resp.diagnostics = diag
    try:
        session_state[LAST_KEY] = record
    except Exception:
        pass


def _apply_cached(resp: CoachResponse, session_state: Any, entry: dict[str, Any]) -> None:
    record = {**entry["record"], "cache_hit": True, "cost_usd": 0.0}
    if entry.get("enrichment"):
        resp.enrichment = dict(entry["enrichment"])
    _record(resp, session_state, record)


def maybe_enrich_song_coaching(
    req: CoachRequest,
    resp: CoachResponse,
    session_state: Any,
    *,
    transport_factory: Callable[[str], ClaudeTransport] | None = None,
    settings: ClaudeSettings | None = None,
) -> CoachResponse:
    """Append validated Claude guidance to `resp.enrichment`; on any failure return `resp` unchanged."""
    try:
        return _enrich(req, resp, session_state, transport_factory, settings)
    except Exception as exc:  # noqa: BLE001 - enrichment must never break the deterministic answer
        try:
            _record(resp, session_state, {"status": "internal_error", "error_type": type(exc).__name__})
        except Exception:
            pass
        return resp


def _enrich(
    req: CoachRequest,
    resp: CoachResponse,
    session_state: Any,
    transport_factory: Callable[[str], ClaudeTransport] | None,
    settings: ClaudeSettings | None,
) -> CoachResponse:
    cfg = settings or load_claude_settings()
    enabled, gate_reason = enrichment_gate(cfg, session_state)
    if not enabled:
        if gate_reason in {"dev_toggle_off", "unpriced_model"}:
            _record(resp, session_state, {"status": "skipped", "reason": gate_reason}, diagnostics=False)
        return resp

    facts, skip_reason = build_fact_sheet(req, resp)
    if facts is None:
        _record(resp, session_state, {"status": "skipped", "reason": skip_reason})
        return resp

    fingerprint = facts.fingerprint(cfg.model)
    cache = session_state.get(CACHE_KEY)
    if not isinstance(cache, dict):
        cache = {}
        session_state[CACHE_KEY] = cache
    if fingerprint in cache:
        _apply_cached(resp, session_state, cache[fingerprint])
        return resp

    from anthropic_secrets_config import resolve_anthropic_api_key

    api_key, _probe = resolve_anthropic_api_key()
    base_record: dict[str, Any] = {"model": cfg.model, "fingerprint": fingerprint, "cache_hit": False}
    if not api_key:
        _record(resp, session_state, {**base_record, "status": "skipped", "reason": "no_api_key"})
        return resp

    try:
        transport = (transport_factory or AnthropicTransport)(api_key)
    except TransportError as exc:
        _record(resp, session_state, {**base_record, "status": "skipped", "reason": exc.kind})
        return resp

    sid = session_state.get(SESSION_ID_KEY)
    if not sid:
        sid = new_session_id()
        session_state[SESSION_ID_KEY] = sid

    user_prompt = _build_user_prompt(facts)
    worst_case = estimate_worst_case_micro_usd(
        cfg.model,
        prompt_chars=len(SYSTEM_PROMPT) + len(user_prompt),
        max_output_tokens=cfg.max_output_tokens,
    )
    try:
        reservation = reserve_budget(
            cfg,
            session_id=sid,
            fingerprint=fingerprint,
            intent=req.intent.value,
            model=cfg.model,
            worst_case_micro_usd=worst_case,
        )
    except BudgetRefused as exc:
        _record(resp, session_state, {**base_record, "status": "refused", "reason": exc.reason})
        return resp
    except LedgerError as exc:
        _record(resp, session_state, {**base_record, "status": "refused", "reason": f"ledger_unavailable:{exc}"})
        return resp

    return _call_and_finish(
        resp, session_state, cfg, facts, transport, reservation, base_record, user_prompt, cache, fingerprint
    )


def _call_and_finish(
    resp: CoachResponse,
    session_state: Any,
    cfg: ClaudeSettings,
    facts: FactSheet,
    transport: ClaudeTransport,
    reservation: Reservation,
    base_record: dict[str, Any],
    user_prompt: str,
    cache: dict[str, Any],
    fingerprint: str,
) -> CoachResponse:
    degraded = False
    try:
        result = transport.complete(
            model=cfg.model,
            system=SYSTEM_PROMPT,
            user=user_prompt,
            schema=ENRICHMENT_JSON_SCHEMA,
            max_output_tokens=cfg.max_output_tokens,
            effort=cfg.effort,
            timeout_s=cfg.timeout_s,
        )
    except TransportError as exc:
        status = f"api_error:{exc.kind}"
        cost = 0
        try:
            if exc.billed == "no":
                release(reservation, status=status, error_type=exc.error_type)
            else:
                cost = settle(
                    reservation,
                    model=cfg.model,
                    usage={},
                    request_id="",
                    status=f"billing_unknown:{exc.kind}",
                    force_cost_micro_usd=reservation.worst_case_micro_usd,
                )
        except LedgerError:
            degraded = True
        record = {
            **base_record,
            "status": status,
            "error_type": exc.error_type,
            "cost_usd": micro_to_usd(cost),
            "ledger_degraded": degraded,
        }
        if exc.billed != "no":
            cache[fingerprint] = {"record": record, "enrichment": None}
        _record(resp, session_state, record)
        return resp

    usage = dict(result.usage)
    cost_forced: int | None = None
    try:
        cost = compute_cost_micro_usd(cfg.model, usage)
    except (ValueError, LedgerError):
        cost = reservation.worst_case_micro_usd
        cost_forced = cost

    enrichment_out: dict[str, Any] | None = None
    violations: tuple[str, ...] = ()
    if result.stop_reason == "refusal":
        status, validation = "refusal", "n/a"
    elif result.stop_reason != "end_turn":
        status, validation = f"incomplete:{result.stop_reason or 'unknown'}", "n/a"
    else:
        try:
            payload = parse_payload_text(result.text)
        except ValueError:
            payload, status, validation = None, "invalid_json", "rejected"
        else:
            checked = validate_enrichment(payload, facts)
            if checked.ok and checked.enrichment is not None:
                status, validation = "accepted", "accepted"
                enrichment_out = {
                    **checked.enrichment.as_dict(),
                    "model": cfg.model,
                }
            else:
                status, validation, violations = "rejected", "rejected", checked.violations

    try:
        settle(
            reservation,
            model=cfg.model,
            usage=usage,
            request_id=result.request_id,
            status=status,
            violations=violations,
            force_cost_micro_usd=cost_forced,
        )
    except (LedgerError, ValueError):
        degraded = True

    record = {
        **base_record,
        "status": status,
        "validation": validation,
        "violations": list(violations),
        "request_id": result.request_id,
        "stop_reason": result.stop_reason,
        "usage": {k: int(v) for k, v in usage.items()},
        "cost_usd": micro_to_usd(cost),
        "ledger_degraded": degraded,
    }
    cache[fingerprint] = {"record": record, "enrichment": enrichment_out}
    if enrichment_out is not None:
        resp.enrichment = dict(enrichment_out)
    _record(resp, session_state, record)
    return resp
