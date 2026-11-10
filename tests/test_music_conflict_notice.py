"""Duplicate presentation must not clear genuine conflicts or dirty workspace state."""
from copy import deepcopy
from music_conflict_notice import show_workspace_conflict_once
from music_workspace_conditional_cloud_write import (
    ITEM8_VIOLATIONS_CURRENT_ATTEMPT_KEY, VIOLATION_DEVICE_APPLIED_NOT_INITIALIZED,
    STALE_WRITE_USER_MESSAGE,
)


class FakeSt:
    def __init__(self, state):
        self.session_state = state
        self.messages = []
    def warning(self, message):
        self.messages.append(message)


def test_one_notice_per_run_preserves_real_conflict_and_dirty_workspace():
    state = {'workspace_id': 'guest', '_suite_cloud_user_hint': 'disposable', '_script_run_seq': 1,
             ITEM8_VIOLATIONS_CURRENT_ATTEMPT_KEY: ['REAL_CONFLICT'],
             '_music_workspace_dirty': True, 'cpl_saved_progressions': {'QA song': {'key': 'D'}}}
    baseline = deepcopy(state)
    st = FakeSt(state)
    assert show_workspace_conflict_once(st)
    assert not show_workspace_conflict_once(st)
    assert st.messages == [STALE_WRITE_USER_MESSAGE]
    assert {k: state[k] for k in baseline} == baseline
    state['_script_run_seq'] = 2
    assert show_workspace_conflict_once(st)
    assert len(st.messages) == 2
    assert state['_music_workspace_dirty']


def test_incomplete_hydration_message_keeps_save_protection_and_scope_isolation():
    state = {'workspace_id': 'guest', '_suite_cloud_user_hint': 'disposable', '_script_run_seq': 1,
             ITEM8_VIOLATIONS_CURRENT_ATTEMPT_KEY: [VIOLATION_DEVICE_APPLIED_NOT_INITIALIZED],
             '_music_workspace_dirty': True}
    st = FakeSt(state)
    assert show_workspace_conflict_once(st)
    assert 'Saving is paused' in st.messages[-1]
    assert 'unsaved edits have not been discarded' in st.messages[-1]
    assert not show_workspace_conflict_once(st)
    state['workspace_id'] = 'other-disposable'
    assert show_workspace_conflict_once(st)
    assert state[ITEM8_VIOLATIONS_CURRENT_ATTEMPT_KEY] == [VIOLATION_DEVICE_APPLIED_NOT_INITIALIZED]
    assert state['_music_workspace_dirty']
