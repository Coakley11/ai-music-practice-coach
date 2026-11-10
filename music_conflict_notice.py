"""Render one current conflict notice per script run without changing write guards."""
def show_workspace_conflict_once(st):
    from music_workspace_conditional_cloud_write import (
        STALE_WRITE_USER_MESSAGE, ITEM8_VIOLATIONS_CURRENT_ATTEMPT_KEY,
        VIOLATION_DEVICE_APPLIED_NOT_INITIALIZED,
    )
    ss = st.session_state
    token = (str(ss.get('_suite_active_workspace_id') or ss.get('workspace_id') or ''),
             str(ss.get('_suite_cloud_user_hint') or ''), int(ss.get('_script_run_seq') or 0))
    if ss.get('_music_conflict_notice_rendered') == token:
        return False
    incomplete = VIOLATION_DEVICE_APPLIED_NOT_INITIALIZED in (ss.get(ITEM8_VIOLATIONS_CURRENT_ATTEMPT_KEY) or [])
    message = ('Your saved workspace has not finished restoring. Saving is paused to protect existing data. '
               'Refresh to retry; your unsaved edits have not been discarded.' if incomplete else STALE_WRITE_USER_MESSAGE)
    st.warning(message)
    ss['_music_conflict_notice_rendered'] = token
    return True
