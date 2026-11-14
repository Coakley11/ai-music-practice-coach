"""Explicit unsupported responses; no generic exercise masquerades as a study."""
import re
from music_coach_ami import warmup_plan as wp
from music_coach_ami.sax_capabilities import SAX


def handle(question, session, ami_ctx=None):
    q = question.lower()
    if not re.search(r'\baltissimo\b|\bovertones?\b|\balternate[ -]+finger(?:ing)?s?\b', q):
        return None
    req = wp.parse_request(question)
    page, _ = wp._page_values(question, session, ami_ctx)
    p, _, facts = wp.resolve_player(req, session, page, req['key'] or getattr(page, 'current_practice_key', '') or 'C')
    if p is None or p.key not in SAX: return None  # Preserve other instrument owners.
    # The ordinary app resolver can default to alto when the selector is absent.
    # That fallback is not verified instrument identity for a future technique.
    from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY
    from music_coach_ami.session_access import as_session_mapping
    selected = as_session_mapping(session).get(SELECTED_TRANSPOSING_INSTRUMENT_KEY, '')
    facts['sax_assumed'] = not bool(req.get('sax_type_word') or wp._spec_for_ttype(selected))
    from music_coach_ami.sax_conversation import reply
    plan = wp.current(session)
    technique = 'altissimo' if 'altissimo' in q else 'overtone' if 'overtone' in q else 'alternate-fingering'
    text = (f'{technique.capitalize()} instruction is not supported by the current verified saxophone engine. '
        'It requires source-reviewed, instrument/model-specific data and independent expert validation; '
        'optional keywork or Advanced level does not establish readiness. '
        'No exercise changed; any displayed score is the existing exercise, not the requested specialized study. ')
    if facts.get('sax_assumed'):
        text += 'Choose soprano, alto, tenor or baritone saxophone before a future instrument-specific lookup. '
    label = 'saxophone' if facts.get('sax_assumed') else p.key+' sax'
    text += f'For currently supported practice, ask for an ordinary {label} articulation or interval exercise.'
    if plan and plan['spec'].get('single'):
        from music_coach_ami.flexible_single import _reply
        response = _reply(text, plan, session, 'unsupported_sax')
    else:
        response = reply(plan, session, text)
    response.diagnostics.update(single_exercise_failed='unsupported_sax',
        specialized_generation_supported=False, capability_technique=technique)
    return response
