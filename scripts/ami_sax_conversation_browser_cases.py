"""Real-app selected-item and chart-interval acceptance, including native SVG facts."""
import copy
from fractions import Fraction
from tests.song_oracle import read_tune
from tests.test_abc_bar_accidentals import read_abc
from tests.test_ami_sax_conversation import independent


def run(page,request,select,out):
    def ask(q,cue,tag):
        r,staff=request(page,q,cue,'sax2-'+tag)
        assert r['before_settings']==r['settings'], 'Coach request changed sidebar settings'
        p=r['plan'];view=r['history'].get('view') or {};rows=p['items']
        if view.get('mode')=='item':rows=[rows[view['index']]]
        for row,actual in zip(rows,staff):
            assert read_abc(row['abc'].replace('(','').replace(')',''))==row['written_midi']
            assert row['sounding_midi']==[m-row.get('offset',p['player']['offset']) for m in row['written_midi']]
            assert all(58<=m<=89 for m in row['written_midi'])
            tune=[e for e in read_tune(row['abc']) if e[2] is not None]
            assert [n['duration'] for n in actual['notes']]==[float(e[1]/4) for e in tune]
            for n,art in zip(actual['notes'],row['articulations']):
                dec=n.get('decoration') or []
                assert ('accent' in dec)==('accent' in art)
                assert ('staccato' in dec)==('staccato' in art)
            groups=row['slur_groups'];starts=[];ends=[]
            for i,n in enumerate(actual['notes']):
                if any([n.get('startSlur')]+[p.get('startSlur') for p in n['pitches']]):starts.append(i)
                if any([n.get('endSlur')]+[p.get('endSlur') for p in n['pitches']]):ends.append(i)
            assert starts==[i for i,g in enumerate(groups) if g and (i==0 or groups[i-1]!=g)]
            assert ends==[i for i,g in enumerate(groups) if g and (i==len(groups)-1 or groups[i+1]!=g)]
            if row.get('meta',{}).get('sax_chart'):
                meta=row['meta'];song=p['spec']['song'];section=meta['chart_section']
                # The independent chart oracle reads actual ABC, never generator interval labels.
                if meta['chart_bars']==[1,len(song['sections'][section])]:
                    independent(row,song,section,row['offset'],row['sax_options']['interval'],row['sax_options'].get('chart_approach',False))
        return r
    def isolated(old,new,index):
        index%=len(old['plan']['items'])
        assert old['settings']==new['settings']
        for i,row in enumerate(old['plan']['items']):
            if i!=index:assert new['plan']['items'][i]==row
        assert new['plan']['items'][index]['reps']==old['plan']['items'][index]['reps']
        row=new['plan']['items'][index]
        if row['instrument']!=new['plan']['player']['key'] and not row.get('meta',{}).get('sax_chart'):
            assert row['key'] in row['title'], 'Adapted notation title has a stale written key'
    def catalog(title):
        import walk_guitar_shape_key as catalog_ui,walk_creative_backing_matrix as existing_ui
        catalog_ui.OUT=out/'catalog';existing_ui.OUT=out/'catalog';catalog_ui.OUT.mkdir(exist_ok=True)
        assert catalog_ui.pick_song(page,[],title,'Jazz')
        page.locator('.st-key-studio_quick_nav_btn_practice button:visible').first.click()
        page.get_by_test_id('stMainBlockContainer').get_by_role('textbox',name='Question',exact=True).wait_for(timeout=90000)
    select(page,'Instrument','Saxophone');select(page,'Level','Intermediate');select(page,'Focus','Articulation')
    a=ask('Give me a ten-minute advanced alto saxophone technique warmup.','10-minute Advanced','01-routine')
    for q,tag,i in [
        ('Make exercise three more difficult.','02-harder',2),
        ('Change the intervals in exercise two to fourths.','03-fourths',1),
        ('Slur every two notes in the first exercise.','04-slurs',0),
        ('Make the last exercise slower.','05-slower',-1),
        ('Keep the notes in exercise three but change the rhythm.','06-rhythm',2),
        ('Adapt exercise three for tenor sax.','07-tenor',2),
        ('Add accents to the last exercise.','08-accents',-1)]:
        b=ask(q,'Updated exercise',tag);isolated(a,b,i);a=b
    why=ask('Explain what exercise two is developing.','Exercise 2:','09-explain');assert why['plan']==a['plan'] and why['history']==a['history']
    undo=ask('Undo.','Undid your last change','10-undo')
    redo=ask('Redo.','Redid','11-redo');assert redo['plan']==a['plan']
    ambiguous=ask('Add accents to the interval exercise.','more than one exercise','12-ambiguous');assert ambiguous['plan']==a['plan'] and ambiguous['history']==a['history']
    tenor=ask('Give me a five-minute tenor sax repeated-note tonguing warmup.','tenor saxophone warmup','13-tenor-routine')
    low=ask('Move exercise one into a lower register.','Updated exercise 1','14-tenor-register');isolated(tenor,low,0)
    marked=ask('Use staccato in the first exercise.','Updated exercise 1','15-tenor-staccato');isolated(low,marked,0)
    catalog('Blue Bossa')
    blue=ask('Give me advanced alto sax fourths over Blue Bossa, first four bars.','Chord-tone fourths','16-blue-fourths')
    assert blue['plan']['items'][0]['meta']['chart_bars']==[1,4]
    b6=ask('Change the fourths to sixths.','Updated exercise 1','17-blue-sixths');assert b6['settings']==blue['settings']
    bc=ask('Use sixths and chromatic approaches over the changes.','Updated exercise 1','18-blue-chromatic');assert bc['settings']==blue['settings']
    catalog('All the Things You Are')
    bridge=ask('Give me advanced tenor sax thirds over the bridge of All the Things You Are.','Chord-tone thirds','19-bridge')
    section=ask('Use the A section instead.','Using A for this item','20-section');assert section['settings']==bridge['settings']
    why=ask('Explain why the notes fit these chords.','Bar 1, beat 1','21-chart-explain');assert why['plan']==section['plan'] and why['history']==section['history']
    u=ask('Undo.','Undid your last change','22-section-undo');assert u['plan']==bridge['plan']
    r=ask('Redo.','Redid','23-section-redo');assert r['plan']==section['plan']
    catalog('Satin Doll')
    sop=ask('Give me advanced soprano sax fourths over the chords of Satin Doll.','Chord-tone fourths','24-soprano-split')
    assert sop['plan']['player']['key']=='soprano'
    catalog('Autumn Leaves')
    bari=ask('Give me advanced baritone sax sixths with chromatic approaches over Autumn Leaves.','Chord-tone sixths','25-baritone')
    assert bari['plan']['player']['key']=='baritone'
