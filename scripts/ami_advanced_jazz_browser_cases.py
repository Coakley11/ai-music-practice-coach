"""Native real-app acceptance for advanced jazz and exact item revisions."""
import copy
from tests.test_ami_advanced_jazz import check
from tests.test_ami_sax_conversation import independent
from music_coach_ami.sax_conversation import restore
from tests.song_oracle import read_tune


def run(page,request,select,out):
    def ask(q,cue,tag):
        r,staff=request(page,q,cue,'jazz-'+tag);assert r['before_settings']==r['settings']
        p=r['plan'];rows=p['items'];view=r['history'].get('view') or {}
        if view.get('mode')=='item':rows=[rows[view['index']]]
        for row,actual in zip(rows,staff):
            b=restore(row['sax_snapshot']);m=row['meta'];song=p['spec']['song']
            check(b,row['abc'],song,m['jazz_section'],row['offset'],m['jazz_bars'])
            assert row['sounding_midi']==[v-row['offset'] for v in row['written_midi']]
            notes=[e for e in read_tune(row['abc']) if e[2] is not None]
            assert [n['duration'] for n in actual['notes']]==[float(e[1]/4) for e in notes]
            for n,art in zip(actual['notes'],row['articulations']):
                dec=n.get('decoration') or []
                assert ('accent' in dec)==('accent' in art) and ('staccato' in dec)==('staccato' in art)
            starts=[];ends=[]
            for i,n in enumerate(actual['notes']):
                if any([n.get('startSlur')]+[v.get('startSlur') for v in n['pitches']]):starts.append(i)
                if any([n.get('endSlur')]+[v.get('endSlur') for v in n['pitches']]):ends.append(i)
            groups=row['slur_groups']
            assert starts==[i for i,g in enumerate(groups) if g and (i==0 or groups[i-1]!=g)]
            assert ends==[i for i,g in enumerate(groups) if g and (i==len(groups)-1 or groups[i+1]!=g)]
        return r
    def isolated(a,b,index):
        assert a['settings']==b['settings']
        assert all(i==index or row==b['plan']['items'][i] for i,row in enumerate(a['plan']['items']))
        assert a['plan']['items'][index]['reps']==b['plan']['items'][index]['reps']
    def catalog(title):
        import walk_guitar_shape_key as catalog_ui,walk_creative_backing_matrix as existing_ui
        catalog_ui.OUT=out/'catalog';existing_ui.OUT=out/'catalog';catalog_ui.OUT.mkdir(exist_ok=True)
        assert catalog_ui.pick_song(page,[],title,'Jazz')
        page.locator('.st-key-studio_quick_nav_btn_practice button:visible').first.click()
        page.get_by_test_id('stMainBlockContainer').get_by_role('textbox',name='Question',exact=True).wait_for(timeout=90000)
    select(page,'Instrument','Saxophone');select(page,'Level','Intermediate');select(page,'Focus','Articulation');catalog('Blue Bossa')
    a=ask('Give me an advanced alto sax arpeggio permutation over Blue Bossa.','Jazz skip chord-tone permutation','01-permutation');assert len(a['plan']['items'])==1
    a=ask('Start each arpeggio on the third.','Updated jazz exercise 1','02-third')
    b=ask('Add chromatic approaches but keep the chord-tone targets.','Updated jazz exercise 1','03-targets')
    c=ask('Make the exercise more bebop-oriented.','Updated jazz exercise 1','04-bebop')
    why=ask('Explain why those notes work.','Bar 1, beat 1','05-explain');assert why['plan']==c['plan'] and why['history']==c['history']
    u=ask('Undo.','Undid your last change','06-undo');assert u['plan']==b['plan']
    r=ask('Redo.','Redid','07-redo');assert r['plan']==c['plan']
    n=ask('Give me advanced alto sax jazz patterns using 3-5-7-9 over Blue Bossa, first four bars.','Jazz 3-5-7-9','08-ninths');assert len(n['plan']['items'])==1
    refused=ask('Give me alto sax jazz patterns using 3-5-7-9 over Blue Bossa.','not named','08b-ninth-refusal');assert refused['plan']==n['plan'] and refused['history']==n['history']
    refused=ask('Give me alto sax jazz thirds and fourths over Blue Bossa.','G7#5','08c-interval-refusal');assert refused['plan']==n['plan'] and refused['history']==n['history']
    rhythm=ask('Keep the notes but alter the rhythm.','Updated jazz exercise 1','09-rhythm');assert rhythm['plan']['items'][0]['written_midi']==n['plan']['items'][0]['written_midi']
    ask('Make a finger-buster that changes direction over each chord.','alternating cells','10-direction')
    warm=ask('Give me a ten-minute alto sax jazz improvisation warmup over Blue Bossa.','10-minute Advanced','11-warmup');assert len(warm['plan']['items'])>=3
    a=ask('Make the second exercise harder.','Updated jazz exercise 2','12-harder');isolated(warm,a,1)
    b=ask('Change the first exercise to enclosures.','Updated jazz exercise 1','13-enclosure');isolated(a,b,0)
    c=ask('Keep the notes in exercise two but alter the rhythm.','Updated jazz exercise 2','14-item-rhythm');isolated(b,c,1)
    adapted=ask('Make exercise three suitable for tenor sax.','Updated jazz exercise 3','15-tenor');isolated(c,adapted,2);assert adapted['plan']['items'][2]['instrument']=='tenor'
    why=ask('Explain why those notes work.','Bar 1, beat 1','16-item-explain');assert why['plan']==adapted['plan'] and why['history']==adapted['history']
    u=ask('Undo.','Undid your last change','17-item-undo');assert u['plan']==c['plan']
    r=ask('Redo.','Redid','18-item-redo');assert r['plan']==adapted['plan']
    catalog('All the Things You Are')
    bridge=ask('Give me an advanced tenor sax jazz technical pattern over the bridge of All the Things You Are.','Jazz skip','19-bridge')
    section=ask('Use the A section instead.','Using A for this item','20-section');assert section['settings']==bridge['settings']
    why=ask('Explain why those notes work.','Bar 1, beat 1','21-chart-explain');assert why['plan']==section['plan'] and why['history']==section['history']
    catalog('Satin Doll')
    sop=ask('Give me an advanced soprano sax jazz anticipation exercise in sixteenth notes over Satin Doll.','Jazz untied anticipations','22-soprano');assert sop['plan']['player']['key']=='soprano'
    catalog('Autumn Leaves')
    bari=ask('Give me an advanced baritone sax jazz double-chromatic approach exercise targeting the third over Autumn Leaves.','Jazz double approaches','23-baritone');assert bari['plan']['player']['key']=='baritone'
    ask('Give me an advanced alto sax jazz pattern with wide leaps and stepwise resolutions over Autumn Leaves.','Chord-tone sixths','24-interval-steps')
