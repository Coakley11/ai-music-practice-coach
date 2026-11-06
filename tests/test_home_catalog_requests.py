from copy import deepcopy
from home_destinations import apply_home_navigation, destination_by_key
from songs.picker_session import apply_home_catalog_request, compose_browse_results, request_clear_browse_filters, apply_picker_session_resets

ROWS=[{'title':'Pop song','artist':'A','genre':'Pop'}, {'title':'Jazz song','artist':'B','genre':'Jazz'}, {'title':'Rock song','artist':'C','genre':'Rock'}]


def test_home_genre_clears_stale_contributions_and_preserves_source():
    for source in ('custom::mine','composition::mine'):
        state={'studio_page':'home','active_catalog_pick_key':source,'display_key':'Eb',
               'selected_song':{'title':'My music'},'song_picker_active_source':'Custom',
               'song_search_text':'Rock','workspace_genre_filters':['Rock'],
               'song_picker_favorites_only':True,'browse_excluded_pick_keys':['hidden']}
        musical={k:deepcopy(state[k]) for k in ('active_catalog_pick_key','display_key','selected_song','song_picker_active_source')}
        apply_home_navigation(state,destination_by_key('discover_pop'),navigate=lambda s,p: s.update(studio_page=p) or True)
        apply_home_catalog_request(state,['Jazz','Pop','Rock'])
        assert state['workspace_genre_filters']==['Pop']
        assert state['song_search_text']==''
        assert not state['song_picker_favorites_only']
        assert not state['browse_excluded_pick_keys']
        assert {k:state[k] for k in musical}==musical
        assert [r['genre'] for r in compose_browse_results(ROWS,genres=state['workspace_genre_filters'])]==['Pop']


def test_entire_catalog_then_ordinary_clear_still_empty():
    state={'_home_catalog_request':'all'}
    apply_home_catalog_request(state,['Jazz','Pop','Rock'])
    assert len(compose_browse_results(ROWS,genres=state['workspace_genre_filters']))==3
    request_clear_browse_filters(state); apply_picker_session_resets(state)
    assert compose_browse_results(ROWS,genres=state['workspace_genre_filters'])==[]
    assert len(compose_browse_results(ROWS,query='Rock',genres=['Pop']))==2


def test_key_cycle_only_requests_controls():
    state={}
    apply_home_navigation(state,destination_by_key('more_keycycle'),navigate=lambda s,p: s.update(studio_page=p) or True)
    assert state=={'studio_page':'backing','_home_open_key_cycle':True}

def test_real_navigation_preserves_custom_and_composition_identity():
    for pick in ('custom::mine', 'composition::mine'):
        state={'studio_page':'home', 'active_catalog_pick_key':pick,
               'selected_song':{'title':'Owned song','pick_key':pick},
               'display_key':'Eb','instrument':'Clarinet',
               'active_music_source':'custom_progression' if pick.startswith('custom') else 'composition_song'}
        before=deepcopy(state)
        apply_home_navigation(state,destination_by_key('discover_jazz'))
        apply_home_catalog_request(state,['Pop','Jazz'])
        for key in before:
            if key!='studio_page':
                assert state[key]==before[key]
        assert state['studio_page']=='picker'


def test_repeated_explicit_home_clicks_are_not_automatic_rerun_loops():
    from music_rerun_loop_guard import should_block_rerun
    state={}
    for _ in range(5):
        apply_home_navigation(state,destination_by_key('discover_all'),navigate=lambda s,p: s.update(studio_page=p) or True)
        assert not should_block_rerun(state,reason='home_nav',fingerprint='same-picker-destination')


def test_creative_navigation_survives_a_previous_tool_canonical_restore():
    from creative_tab_tool_persistence import canonical_creative_selector_value
    state={'studio_page':'home', '_pending_history_creative_dest':'creative::Missions'}
    for card, expected in [('more_missions','Missions'), ('more_sbi','Song-Aware Coaching'), ('more_missions','Missions')]:
        apply_home_navigation(state,destination_by_key(card),navigate=lambda s,p: s.update(studio_page=p) or True)
        assert '_pending_history_creative_dest' not in state
        assert canonical_creative_selector_value(state,'improv_intelligence_tab')==expected
        assert canonical_creative_selector_value(state,'creative_lab_analysis_mode')=='Improvisation Intelligence'
