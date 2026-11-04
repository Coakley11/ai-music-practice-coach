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
