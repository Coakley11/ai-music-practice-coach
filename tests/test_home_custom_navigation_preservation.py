"""Home -> Custom visits are navigation, not source/key activation."""
from copy import deepcopy
from unittest.mock import patch
import pytest

from custom_progression_lab import (
    CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET,
    cpl_workspace_practice_key,
    default_active_progression,
)
from music_sidebar_policy import apply_page_defaults
from songs.music_source import (
    EXPLICIT_MUSIC_SOURCE_CHOICE_KEY, USER_CATALOG_SOURCE_CHOICE_KEY,
    SOURCE_CATALOG, SOURCE_CUSTOM, custom_selected_song_record,
)
from studio_nav_history import navigate_studio_page
from studio_page_persistence import handle_studio_page_transition


@pytest.mark.parametrize('source', [SOURCE_CATALOG, SOURCE_CUSTOM])
def test_home_custom_roundtrip_preserves_active_song_and_independent_keys(source):
    trial = default_active_progression()
    trial.update(id='home-custom-fixture', name='Trial Song', original_key_center='D')
    trial['original_sections']['Verse'] = [{'chord': 'D', 'bars': 2}]
    trial['lyrics_by_section'] = {'Verse': 'Disposable lyrics'}
    catalog_pick = 'Pop\x1fCatalog fixture'
    custom_pick = 'custom::home-custom-fixture'
    catalog_song = {'title': 'Catalog fixture', 'key': 'G', 'pick_key': catalog_pick}
    is_catalog = source == SOURCE_CATALOG
    state = {
        'studio_page': 'home', 'workspace_id': 'guest',
        'active_music_source': source,
        EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: source,
        USER_CATALOG_SOURCE_CHOICE_KEY: is_catalog,
        'active_catalog_pick_key': catalog_pick if is_catalog else custom_pick,
        'selected_song': catalog_song if is_catalog else custom_selected_song_record(trial),
        'display_key': 'B' if is_catalog else 'C',
        CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET: 'C',
        'practice_key_by_source': {catalog_pick: 'B', custom_pick: 'C'},
        'practice_key_user_override_picks': [catalog_pick, custom_pick],
        'cpl_active_progression': trial, 'cpl_saved_progressions': {'Trial Song': trial},
        'composer_saved_compositions': {'piece': {'id': 'piece', 'title': 'Saved composition'}},
        'mt_tracks': {'A': b'disposable-audio'}, 'instrument': 'Piano',
        # Simulate an obsolete snapshot that must not restore global ownership.
        '_studio_page_snapshots': {'custom': {'display_key': 'F#',
            'active_music_source': SOURCE_CUSTOM, 'active_catalog_pick_key': 'custom::obsolete'}},
    }
    protected = [k for k in state if not k.startswith('_studio') and k != 'studio_page']
    baseline = {k: deepcopy(state[k]) for k in protected}
    with patch('music_persistent_state.after_studio_page_change') as save:
        for destination in ('custom', 'home', 'custom'):
            assert navigate_studio_page(state, destination)
            handle_studio_page_transition(state)
            apply_page_defaults(state, destination)
            assert cpl_workspace_practice_key(state, trial) == 'C'
            assert {k: state[k] for k in protected} == baseline
        assert save.call_count == 3
