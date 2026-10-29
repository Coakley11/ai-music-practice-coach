"""Canonical Catalog identity, Favorite migration, and additive Browse acceptance."""
from copy import deepcopy
from songs.picker_session import canonical_favorite_pick_keys, compose_browse_results, request_clear_browse_filters, apply_picker_session_resets
from song_catalog.catalog import load_song_catalog, format_pick_key, search_records
from songs.music_source import last_authoritative_catalog_snapshot, queue_last_catalog_restore, apply_pending_previous_catalog_restore_before_widgets
from tests.test_r11_key_convergence_and_index import _Base, _FakeSt


def rows():return load_song_catalog()[3]
def pick(r):return format_pick_key(r['genre'],f"{r['title']} \u2014 {r['artist']}")

def test_legacy_favorites_share_canonical_count_filter_and_identity():
    records=rows();bossa=next(r for r in records if r['title']=='Blue Bossa')
    actual=canonical_favorite_pick_keys(['Blue Bossa',pick(bossa),'Jazz\x1fBlue Bossa','composition::bad'],records)
    assert actual==[pick(bossa)]
    assert [pick(r) for r in compose_browse_results(records,favorite_pick_keys=actual,favorites_enabled=True)]==actual


def test_search_genres_favorites_union_has_no_duplicates_or_hidden_members():
    records=rows();favs=[pick(r) for r in records if r['title'] in ('Blue Bossa','Perfect','Let It Be')]
    actual=compose_browse_results(records,query='Shalom',genres=['Jazz','Rock'],favorite_pick_keys=favs,favorites_enabled=True)
    expected={pick(r) for r in search_records(records,'Shalom')}|{pick(r) for r in records if r['genre'] in ('Jazz','Rock')}|set(favs)
    assert len(actual)==len(expected)
    assert {pick(r) for r in actual}==expected


def test_clear_filters_removes_hidden_compatibility_filters_without_unfavoriting():
    ss={'song_search_text':'Shalom','workspace_genre_filters':['Jazz'],'song_picker_favorites_only':True,
        'catalog_favorite_pick_keys':['favorite'],'chart_library_mode':'Core library','song_picker_chart_status':'Curated highlights','song_picker_level_filter':'Advanced'}
    request_clear_browse_filters(ss);apply_picker_session_resets(ss)
    assert ss['song_search_text']=='' and ss['workspace_genre_filters']==[] and ss['song_picker_favorites_only'] is False
    assert ss['catalog_favorite_pick_keys']==['favorite']
    assert ss['chart_library_mode']=='Full library' and ss['song_picker_chart_status']=='All songs' and ss['song_picker_level_filter']=='Any level'


class TestLastCatalogSelection(_Base):
    def test_load_last_includes_current_identity_and_restores_after_custom(self):
        ss=self.new_session();pk=self.activate_catalog(ss,'Jazz','Blue Bossa \u2014 Kenny Dorham')
        assert last_authoritative_catalog_snapshot(ss)['pick_key']==pk
        self.activate_custom(ss,chords=('D','A','Bm','G'))
        assert last_authoritative_catalog_snapshot(ss)['pick_key']==pk
        queue_last_catalog_restore(_FakeSt(ss))
        assert apply_pending_previous_catalog_restore_before_widgets(_FakeSt(ss),song_picker_catalog=self.picker,song_library=self.library,invalidate_backing=lambda _:None)
        self.converge(ss)
        assert self.owner(ss)=='catalog' and ss['active_catalog_pick_key']==pk
        assert self.original_key(ss)=='Cm'

    def test_composition_and_now_singing_do_not_replace_last_catalog_identity(self):
        import karaoke_mode as km
        ss=self.new_session();pk=self.activate_catalog(ss,'Jazz','Blue Bossa \u2014 Kenny Dorham')
        self.activate_composition(ss)
        before=deepcopy(last_authoritative_catalog_snapshot(ss))
        assert before['pick_key']==pk
        ss['instrument']='Voice'
        for title in ('Shallow','Perfect'):
            km.add_to_queue(ss,'Pop\x1f'+title,title=title,artist='',practice_key='G',bpm=100)
        km.start_session(ss);km.advance_session(ss,skip_repeats=True)
        assert last_authoritative_catalog_snapshot(ss)==before

class TestExplicitCustomClickAfterCatalog(_Base):
    def test_presented_catalog_radio_click_is_not_a_stale_custom_echo(self):
        from songs.music_source import on_song_picker_source_change,SONG_PICKER_PRESENTED_SOURCE_KEY,SONG_PICKER_SOURCE_CATALOG,SONG_PICKER_SOURCE_CUSTOM,CATALOG_SWITCH_APPLIED_THIS_RUN_KEY
        ss=self.new_session();self.activate_custom(ss,chords=('D','A','Bm','G'))
        self.activate_catalog(ss,'Jazz','Blue Bossa \u2014 Kenny Dorham')
        ss['studio_page']='picker'
        ss[SONG_PICKER_PRESENTED_SOURCE_KEY]=SONG_PICKER_SOURCE_CATALOG
        ss['song_picker_active_source']=SONG_PICKER_SOURCE_CUSTOM
        ss[CATALOG_SWITCH_APPLIED_THIS_RUN_KEY]=ss.get('_script_run_seq',0)
        on_song_picker_source_change(_FakeSt(ss),song_picker_catalog=self.picker,song_library=self.library,invalidate_backing=lambda _:None,in_callback=True)
        assert ss['active_music_source']=='custom_progression'

    def test_old_custom_widget_echo_still_cannot_reclaim_catalog(self):
        from songs.music_source import on_song_picker_source_change,SONG_PICKER_PRESENTED_SOURCE_KEY,SONG_PICKER_SOURCE_CUSTOM,CATALOG_SWITCH_APPLIED_THIS_RUN_KEY
        ss=self.new_session();self.activate_custom(ss,chords=('D','A','Bm','G'))
        pk=self.activate_catalog(ss,'Jazz','Blue Bossa \u2014 Kenny Dorham')
        ss['studio_page']='picker';ss['song_picker_active_source']=SONG_PICKER_SOURCE_CUSTOM
        ss[SONG_PICKER_PRESENTED_SOURCE_KEY]=SONG_PICKER_SOURCE_CUSTOM
        ss[CATALOG_SWITCH_APPLIED_THIS_RUN_KEY]=ss.get('_script_run_seq',0)
        on_song_picker_source_change(_FakeSt(ss),song_picker_catalog=self.picker,song_library=self.library,invalidate_backing=lambda _:None,in_callback=True)
        assert ss['active_music_source']=='catalog_song' and ss['active_catalog_pick_key']==pk
