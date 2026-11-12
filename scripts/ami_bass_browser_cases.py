"""Real app bass acceptance, including actual engraved bass-clef note heads."""
from tests.bass_oracle import check

def run(page,request,select,out,context_only=False):
    def ask(q,cue,tag):
        r,staff=request(page,q,cue,'bass-'+tag)
        p=r['plan']
        if p and p['player']['key']=='bass':
            assert check(p)==[],check(p)
            for score in staff:
                assert 'clef=bass' in score['abc']
                for note in score['notes']:
                    pitch=note['pitches'][0]
                    # C4 is diatonic 0 in ABCJS. Bass-clef G2 bottom line
                    # is vertical position 2, hence the independent +12 offset.
                    assert pitch['verticalPos']==pitch['pitch']+12,(pitch,note)
                    assert note['headPitches']==[pitch['verticalPos']],note
        return r
    if not context_only:
        select(page,'Instrument','Saxophone');select(page,'Level','Beginner');select(page,'Focus','Scales')
        original=ask('Give me an E minor bass scale.','Bass guitar scale','01-scale-override')
        assert original['plan']['items'][0]['written_midi']==[40,42,43,45,47,48,50,52]
        assert original['settings']['instrument']=='Saxophone'
        warm=ask('Give me a beginner bass guitar warmup.','Beginner bass guitar warmup','02-warmup')
        assert not warm['plan']['spec'].get('single') and set(warm['plan']['spec']['families'])=={'scale','intervals','articulation'}
        octave=ask('Give me a bass exercise using octaves.','Bass guitar octaves','03-octaves')
        buster=ask('Give me a bass guitar finger-buster.','Bass guitar buster','04-buster')
        assert buster['plan']['level']=='Advanced' and buster['settings']['level']=='Beginner'
        arp=ask('Give me a difficult bass arpeggio exercise.','Bass guitar arpeggio','05-arpeggio')
        coord=ask('Give me something to improve my bass finger coordination.','Bass guitar coordination','06-coordination')
        assert len({p['string'] for p in coord['plan']['items'][0]['meta']['positions']})==4
        a=ask('Give me an intermediate bass arpeggio in E minor.','Bass guitar arpeggio','07-revision-start')
        harder=ask('Make it harder.','Bass guitar arpeggio','08-harder');assert harder['plan']['level']=='Advanced'
        ask('Move it to a lower register.','Bass guitar arpeggio','09-lower')
        fifth=ask('Start on the fifth.','Bass guitar arpeggio','10-fifth');assert fifth['plan']['items'][0]['sounding_midi'][0]%12==11
        ask('Use octave jumps.','Bass guitar arpeggio','11-octave-jumps')
        ask('Make it descending.','Bass guitar arpeggio','12-descending')
        crossed=ask('Add some string crossings.','Bass guitar arpeggio','13-crossings')
        slow=ask('Make it slower.','Bass guitar arpeggio','14-slower')
        assert slow['plan']['items'][0]['bpm']<crossed['plan']['items'][0]['bpm']
        why=ask('Explain why this pattern works.','verified four-string path','15-explain')
        assert why['plan']==slow['plan'] and why['history']==slow['history']
        undo=ask('Undo.','Restored the exact stored version','16-undo');assert undo['plan']==crossed['plan']
        redo=ask('Redo.','Restored the exact stored version','17-redo');assert redo['plan']==slow['plan']
        invalid=ask('Use slap and harmonics.','outside the supported four-string','18-refusal');assert invalid['plan']==redo['plan']
    select(page,'Instrument','Bass');select(page,'Level','Intermediate');select(page,'Focus','Root Motion')
    fallback=ask('Give me an exercise.','Bass guitar arpeggio','19-sidebar-harmony');assert fallback['plan']['player']['key']=='bass'
    select(page,'Instrument','Saxophone');select(page,'Focus','Articulation')
    art=ask('Give me a bass guitar exercise.','Bass guitar coordination','20-sidebar-articulation');assert art['plan']['spec']['articulation']=='staccato'
    select(page,'Instrument','Bass');select(page,'Focus','Melody')
    melody=ask('Give me an exercise.','Bass guitar scale','21-sidebar-melody');assert melody['plan']['spec']['family']=='scale'
    import walk_guitar_shape_key as catalog_ui
    import walk_creative_backing_matrix as existing_ui
    catalog_ui.OUT=out/'catalog';existing_ui.OUT=out/'catalog';catalog_ui.OUT.mkdir(exist_ok=True)
    assert catalog_ui.pick_song(page,[],'Blue Bossa','Jazz')
    page.locator('.st-key-studio_quick_nav_btn_practice button:visible').first.click()
    page.get_by_test_id('stMainBlockContainer').get_by_role('textbox',name='Question',exact=True).wait_for(timeout=90000)
    song=ask('Give me a bass line over these chord changes.','one chart pass','22-chart')
    assert song['plan']['spec']['song']['title']=='Blue Bossa'
    from music_coach_ami import warmup_song as ws
    from tests.song_oracle import check_chordline
    spec=song['plan']['spec'];sel=spec['song_sel']
    slots=ws.section_slots(spec['song'],sel['section'])
    if sel.get('bars'):slots=slots[sel['bars'][0]-1:sel['bars'][1]]
    assert check_chordline(song['plan']['items'][0]['abc'],slots,12,approach=False)==[]
