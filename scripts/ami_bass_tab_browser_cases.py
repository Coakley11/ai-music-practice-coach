"""Actual staff/TAB DOM, canonical timing, revisions and mobile acceptance."""
import json,re
from tests.bass_tab_oracle import check

def run(page,request,select,out,mobile=False,probe=False):
    def ask(q,cue,tag):
        r,staff=request(page,q,cue,'tab-'+tag)
        p=r['plan'];assert check(p)==[],check(p)
        panel=page.locator('[class*="st-key-music_coach_insight_panel_"]').filter(has_text=q).last
        observed=[]
        for iframe in panel.locator('iframe').all():
            f=iframe.element_handle().content_frame()
            data=f.evaluate('''() => ({status:window.__amiBassTabs,warning:!!document.querySelector('.ami-bass-tab-warning'),width:innerWidth,body:document.body.scrollWidth,
                scores:Array.from(document.querySelectorAll('[id^="coach_abc_paper_"]')).map(p=>({
                    frets:Array.from(p.querySelectorAll('.ami-bass-tab-fret,.ami-bass-tab-rest')).map(g=>({event:+g.dataset.event,bar:+g.dataset.bar,beat:+g.dataset.beat,
                        string:g.dataset.string==='null'?null:+g.dataset.string,fret:g.dataset.fret==='null'?null:+g.dataset.fret,rest:g.classList.contains('ami-bass-tab-rest'),
                        onset:g.dataset.onset,beats:g.dataset.beats,text:g.querySelector('text').textContent,x:+g.querySelector('text').getAttribute('x'),scoreX:+g.dataset.scoreX})),
                    strings:Array.from(p.querySelectorAll('.ami-bass-tab-string')).map(l=>({name:l.dataset.name,y:+l.getAttribute('y1')})),
                    bars:Array.from(p.querySelectorAll('.ami-bass-tab-bar')).map(l=>({x:+l.getAttribute('x1'),scoreX:+l.dataset.scoreX})),
                    scroll:p.parentElement.scrollWidth>p.parentElement.clientWidth
                }))})''')
            assert not data['warning'],data
            assert data['status'] and all(x['ok'] for x in data['status']),data
            for state in data['status']:
                for i,layout in enumerate(state['layouts']):
                    assert layout['tabTop']>=layout['nativeBottom']+4
                    if i:assert layout['nativeTop']>=state['layouts'][i-1]['tabBottom']+4
            assert data['body']<=data['width']+1,('iframe overflow',data['body'],data['width'])
            view=r['history'].get('view',{});rows=p['items']
            if view.get('mode')=='item':rows=[rows[view['index']]]
            for score,row in zip(data['scores'],rows):
                expected=row['meta']['bass_tab']['events'];assert len(score['frets'])==len(expected)
                for actual,event in zip(score['frets'],expected):
                    assert actual['event']==event['id'] and actual['rest']==event['rest']
                    assert actual['string']==event['string'] and actual['fret']==event['fret']
                    assert actual['text']==('rest' if event['rest'] else str(event['fret']))
                    assert actual['onset']=='/'.join(map(str,event['onset'])) and actual['beats']=='/'.join(map(str,event['beats']))
                    assert actual['x']==actual['scoreX']+3
                for i in range(0,len(score['strings']),4):
                    group=score['strings'][i:i+4];assert [x['name'] for x in group]==list('GDAE')
                    assert [x['y'] for x in group]==sorted(x['y'] for x in group)
                assert all(b['x']==b['scoreX'] for b in score['bars'])
                if mobile:assert score['scroll'],'Mobile score should remain readable via contained horizontal scrolling'
            if mobile:
                access=f.evaluate('''() => Array.from(document.querySelectorAll('[id^="coach_abc_paper_"]')).map(p=>{const container=p.parentElement;container.scrollLeft=container.scrollWidth;const last=p.querySelectorAll('.ami-bass-tab-fret,.ami-bass-tab-rest');const r=last[last.length-1].getBoundingClientRect(),c=container.getBoundingClientRect();const visible=r.right<=c.right+2;container.scrollLeft=0;return visible})''')
                assert all(access),'Last TAB event is not reachable by horizontal scrolling'
            observed.append(data)
        (out/('tab-'+tag+'-tab-dom.json')).write_text(json.dumps(observed,indent=2),encoding='utf-8')
        return r
    select(page,'Instrument','Saxophone');select(page,'Level','Intermediate');select(page,'Focus','Scales')
    a=ask('Give me an E minor bass scale.','Bass guitar scale','01-scale')
    if probe:
        refused=ask('Use tied notes.','outside the supported','probe-refusal')
        assert refused['plan']==a['plan'] and refused['history']==a['history']
        shown=ask('Show me the TAB.','same stored passage','probe-show')
        assert shown['plan']==a['plan'] and shown['history']==a['history']
        return
    shown=ask('Show me the TAB.','same stored passage','02-show');assert shown['plan']==a['plan'] and shown['history']==a['history']
    if mobile:
        ask('Give me bass finger coordination.','Bass guitar coordination','03-mobile-coordination')
        ask('Give me a beginner bass guitar warmup.','bass guitar warmup','04-mobile-warmup')
        panel=page.locator('[class*="st-key-music_coach_insight_panel_"]').filter(has_text='Give me a beginner bass guitar warmup.').last
        for i in (1,2):
            panel.get_by_role('button',name='Next exercise',exact=True).click()
            panel.get_by_text(re.compile('Exercise '+str(i)+' of')).first.wait_for(timeout=90000)
        selected=ask('Show me the TAB.','same stored passage','05-mobile-selected')
        assert selected['history']['view']=={'mode':'item','index':1}
        import walk_guitar_shape_key as catalog_ui,walk_creative_backing_matrix as existing_ui
        catalog_ui.OUT=out/'catalog';existing_ui.OUT=out/'catalog';catalog_ui.OUT.mkdir(exist_ok=True)
        page.set_viewport_size({'width':1440,'height':1000})
        assert catalog_ui.pick_song(page,[],'Satin Doll','Jazz')
        page.set_viewport_size({'width':390,'height':844})
        page.locator('.st-key-studio_quick_nav_btn_practice button:visible').first.click()
        page.get_by_test_id('stMainBlockContainer').get_by_role('textbox',name='Question',exact=True).wait_for(timeout=90000)
        chart=ask('Give me a bass line over these chord changes.','one chart pass','06-mobile-split-chart')
        assert any(e['chord'] and e['beat']!=1 for e in chart['plan']['items'][0]['meta']['bass_tab']['events'])
        return
    different=ask('Play this on a different string.','synchronized staff/TAB','03-different')
    assert different['plan']['items'][0]['written_midi']==a['plan']['items'][0]['written_midi']
    assert different['plan']['items'][0]['meta']['positions']!=a['plan']['items'][0]['meta']['positions']
    undo=ask('Undo.','Restored the exact stored version','04-undo');assert undo['plan']==a['plan']
    redo=ask('Redo.','Restored the exact stored version','05-redo');assert redo['plan']==different['plan']
    fast=ask('Make the rhythm faster.','synchronized staff/TAB','06-rhythm')
    assert fast['plan']['items'][0]['meta']['positions']==redo['plan']['items'][0]['meta']['positions']
    ask('Make it harder.','Bass guitar scale','07-harder')
    ask('Move it lower.','Bass guitar scale','08-lower')
    ask('Use more string crossings.','Bass guitar scale','09-crossings')
    ask('Make it descending.','Bass guitar scale','10-descending')
    ask('Use the open strings.','Bass guitar scale','11-open')
    p=ask('Give me advanced bass coordination in position 5.','Bass guitar coordination','12-position')
    assert all(x['hand_low']==5 for x in p['plan']['items'][0]['meta']['positions'])
    ask('Give me an advanced bass scale in E minor on the E string.','Bass guitar scale','13-string')
    ask('Give me a beginner bass guitar warmup.','bass guitar warmup','14-warmup')
    import walk_guitar_shape_key as catalog_ui,walk_creative_backing_matrix as existing_ui
    catalog_ui.OUT=out/'catalog';existing_ui.OUT=out/'catalog';catalog_ui.OUT.mkdir(exist_ok=True)
    assert catalog_ui.pick_song(page,[],'Blue Bossa','Jazz')
    page.locator('.st-key-studio_quick_nav_btn_practice button:visible').first.click()
    page.get_by_test_id('stMainBlockContainer').get_by_role('textbox',name='Question',exact=True).wait_for(timeout=90000)
    ask('Give me a bass line over these chord changes.','one chart pass','15-chart')
