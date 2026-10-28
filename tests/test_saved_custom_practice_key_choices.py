"""Explicit saved Custom choices are source-owned across activation boundaries."""
from copy import deepcopy
import json
from pathlib import Path
from tests.test_r11_key_convergence_and_index import _Base, _FakeSt
from songs.music_source import commit_custom_active_song, custom_pick_key_for
from songs.practice_key_state import get_practice_concert_key, set_practice_concert_key, mark_practice_key_user_override, clear_practice_concert_key

class TestSavedCustomChoices(_Base):
    def test_custom_a_b_a_restores_each_saved_key(self):
        ss=self.new_session()
        a=json.loads(Path('tests/fixtures/continuation_trial_song.json').read_text())
        b=deepcopy(a);b.update(id='continuation-custom-b',name='Custom B',original_key_center='F')
        b['original_sections']={'Verse':[{'chord':'F','bars':1},{'chord':'C','bars':1}]}
        picks=[custom_pick_key_for(x) for x in (a,b)]
        for song,pick,key in ((a,picks[0],'E'),(b,picks[1],'Ab')):
            commit_custom_active_song(_FakeSt(ss),song,invalidate_backing=lambda _:None,reset_practice_to_original=True)
            set_practice_concert_key(ss,key,pick_key=pick,allow_restore_original=True)
            mark_practice_key_user_override(ss,pick)
        for song,pick,key in ((a,picks[0],'E'),(b,picks[1],'Ab'),(a,picks[0],'E')):
            commit_custom_active_song(_FakeSt(ss),song,invalidate_backing=lambda _:None,reset_practice_to_original=True)
            assert get_practice_concert_key(ss,pick_key=pick)==key
            assert ss['concert_key']==key
            assert ss['cpl_active_progression']['original_key_center']==song['original_key_center']

    def test_custom_choice_requires_force_to_clear(self):
        ss=self.new_session();pick='custom::saved'
        set_practice_concert_key(ss,'E',pick_key=pick,allow_restore_original=True)
        mark_practice_key_user_override(ss,pick)
        assert not clear_practice_concert_key(ss,pick)
        assert get_practice_concert_key(ss,pick_key=pick)=='E'
        assert clear_practice_concert_key(ss,pick,force=True)
