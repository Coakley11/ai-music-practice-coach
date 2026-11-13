"""Real-app unsupported-technique, unchanged score and existing-owner acceptance."""
import copy
from tests.test_ami_advanced_jazz import check
from music_coach_ami.sax_conversation import restore

def run(page,request,select,out):
    import walk_guitar_shape_key as catalog_ui,walk_creative_backing_matrix as existing_ui
    catalog_ui.OUT=out/'catalog';existing_ui.OUT=out/'catalog';catalog_ui.OUT.mkdir(exist_ok=True)
    assert catalog_ui.pick_song(page,[],'Blue Bossa','Jazz')
    page.locator('.st-key-studio_quick_nav_btn_practice button:visible').first.click()
    page.get_by_test_id('stMainBlockContainer').get_by_role('textbox',name='Question',exact=True).wait_for(timeout=90000)
    select(page,'Instrument','Saxophone')
    def ask(q,cue,tag):
        r,staff=request(page,q,cue,'capability-'+tag)
        assert r['before_settings']==r['settings']
        if r['plan']['spec'].get('sax',{}).get('jazz'):
            for row in r['plan']['items']:
                check(restore(row['sax_snapshot']),row['abc'],r['plan']['spec']['song'],row['meta']['jazz_section'],row['offset'],row['meta']['jazz_bars'])
        return r
    original=ask('Give me a ten-minute alto sax jazz improvisation warmup over Blue Bossa.','10-minute Advanced','01-warmup')
    selected=ask('Make the second exercise harder.','Updated jazz exercise 2','02-selected')
    assert all(i==1 or row==selected['plan']['items'][i] for i,row in enumerate(original['plan']['items']))
    for tag,q in [('03-altissimo','Give me an altissimo G exercise.'),('04-overtones','Give me an overtone series from low B-flat.'),('05-fingering','Show me alternate fingerings for high F-sharp.')]:
        r=ask(q,'not supported',tag)
        assert r['plan']==selected['plan'] and r['history']==selected['history']
        assert r['response']['diagnostics']['specialized_generation_supported'] is False
        assert 'existing exercise' in r['response']['direct_answer']
    why=ask('Explain why those notes work.','Bar 1, beat 1','06-explain')
    assert why['plan']==selected['plan'] and why['history']==selected['history']
    u=ask('Undo.','Undid your last change','07-undo');assert u['plan']==original['plan']
    r=ask('Redo.','Redid','08-redo');assert r['plan']==selected['plan']
    ordinary=ask('Give me an alto sax articulation exercise.','Alto Saxophone','09-supported')
    assert ordinary['plan']['spec']['sax'] and not ordinary['plan']['spec']['sax'].get('jazz')
    trumpet=ask('Give me a beginner trumpet lip-slur exercise.','lip-slur partial','10-trumpet')
    assert trumpet['plan']['spec']['trumpet'] and trumpet['plan']['items'][0]['written_midi']==[60,67]*2
