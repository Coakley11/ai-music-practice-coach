"""Actual diagrams, independent key-state oracle, staff positions and history."""
import copy,json
from pathlib import Path
O=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/yas280_basic_fingering_oracle.json').read_text())['notes']

def run(page,request,select,out):
    select(page,'Instrument','Saxophone')
    def ask(q,cue,tag):
        r,staff=request(page,q,cue,'fingering-'+tag)
        assert r['before_settings']==r['settings']
        if r['response']['diagnostics'].get('fingering_lookup'):
            n=r['response']['diagnostics']['fingering_instruction'][0]['id']
            assert len(staff)==1 and len(staff[0]['notes'])==1
            assert staff[0]['notes'][0]['pitches'][0]['pitch']=={'G4':4,'A4':5,'B4':6}[n]
        return r
    def visual(note,tag):
        panel=page.locator('[class*="st-key-music_coach_insight_panel_"]').last
        iframe=panel.locator('iframe').first;f=iframe.element_handle().content_frame()
        figure=f.locator('.ami-fingering[data-record="'+note+'"]');figure.wait_for()
        figure.scroll_into_view_if_needed();figure.focus()
        assert figure.evaluate('(e)=>document.activeElement===e')
        assert 'not independently teacher-reviewed' in figure.inner_text()
        observed=figure.evaluate("""e=>({label:e.getAttribute('aria-label'),desc:document.getElementById(e.getAttribute('aria-describedby')).textContent,svg:e.querySelector('svg').getBoundingClientRect().toJSON(),width:innerWidth,body:document.body.scrollWidth,
            keys:[...e.querySelectorAll('[data-key]')].map(k=>({id:k.dataset.key,pressed:k.dataset.pressed,fill:getComputedStyle(k.querySelector('circle')).fill})),
            fonts:[...e.querySelectorAll('svg text')].map(t=>t.getBoundingClientRect().height)})""")
        assert observed['body']<=observed['width']+1 and observed['svg']['width']>=280
        assert observed['svg']['right']<=observed['width']+1 and min(observed['fonts'])>=12
        assert len(observed['keys'])==7
        for key in observed['keys']:
            pressed=key['id'] in O[note]['pressed']
            assert key['pressed']==str(pressed).lower()
            assert key['fill']==('rgb(23, 78, 166)' if pressed else 'rgb(255, 255, 255)')
        assert note in observed['label'] and 'Press:' in observed['desc']
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        figure.screenshot(path=str(out/(tag+'-diagram.png')))
        iframe.screenshot(path=str(out/(tag+'-staff-diagram.png')))
        (out/(tag+'-visual.json')).write_text(json.dumps(observed,indent=2),encoding='utf-8')
        figure.press('Tab');assert f.evaluate("document.activeElement.tagName==='A'")
    missing=ask("What's the fingering for A on alto saxophone?",'Which saxophone model','01-model-needed');assert not missing['plan']
    denied=ask("I do not play a Yamaha YAS-280.",'No model was confirmed','01b-negation');assert not denied['fingering_context']
    uncertain=ask('How do I know if my sax is a YAS-280?','Please identify','01c-uncertain');assert not uncertain['fingering_context']
    model=ask('I play a Yamaha YAS-280.','identified','02-model');assert not model['plan'] and not model['fingering_context']['note']
    for i,n in enumerate(('G4','A4','B4'),3):
        page.set_viewport_size({'width':1440,'height':1000})
        r=ask('Show me the fingering for '+n+'.','written '+n,f'{i:02}-{n}')
        assert not r['plan'] and r['fingering_context']['note']==n
        visual(n,'desktop-'+n)
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(1200)
        visual(n,'mobile-'+n)
    page.set_viewport_size({'width':1440,'height':1000})
    why=ask('Can you explain which keys are pressed?','written B4','06-keys');assert not why['plan']
    staff=ask('Can you show me that note on the staff?','written B4','07-staff');assert not staff['plan']
    lead=ask('Show me a couple of notes leading up to it.','Fingering practice','08-lead');assert lead['plan']['items'][0]['written_midi']==[67,69,71,71]
    slow=ask('Make the exercise slower.','Fingering practice','09-slower');assert slow['plan']['items'][0]['bpm']<lead['plan']['items'][0]['bpm']
    desc=ask('Now make it descending.','Fingering practice','10-descending');assert desc['plan']['items'][0]['written_midi']==[71,71,69,67]
    keys=ask('Explain what keys I need to change.','Left middle: press','11-key-changes');assert keys['plan']==desc['plan'] and keys['history']==desc['history']
    undo=ask('Undo.','Restored the exact stored version','12-undo');assert undo['plan']==slow['plan']
    redo=ask('Redo.','Restored the exact stored version','13-redo');assert redo['plan']==desc['plan']
    easy=ask('Make it easier.','Simplified','14-easier');assert easy['plan']['items'][0]['written_midi']==[71,71]
    undo=ask('Undo.','Restored the exact stored version','15-undo-easier');assert undo['plan']==desc['plan']
    lookup=ask('Show me the fingering for A4.','written A4','16-readonly-A');assert lookup['plan']==desc['plan'] and lookup['history']==undo['history']
    refused=ask('Show me a couple of notes leading up to it.','unavailable','17-unavailable-lead');assert refused['plan']==lookup['plan'] and refused['history']==lookup['history']
    target=ask('Give me a short exercise using it.','Fingering practice','18-target');assert target['plan']['items'][0]['written_midi']==[69]*4
    other=ask('Show the fingering for B4.','written B4','18b-other-note');assert other['plan']==target['plan']
    otherkeys=ask('Can you explain which keys are pressed?','written B4','18c-other-keys');assert otherkeys['plan']==target['plan'] and otherkeys['history']==target['history']
    assert otherkeys['response']['diagnostics']['fingering_instruction'][0]['id']=='B4'
    exercise=ask('Explain which keys change in the exercise.','Key changes','18d-exercise-keys');assert exercise['plan']==target['plan'] and exercise['history']==target['history']
    assert exercise['response']['diagnostics']['fingering_instruction'][0]['id']=='A4'
    refocus=ask('Show the fingering for A4.','written A4','18e-refocus');assert refocus['plan']==target['plan']
    for tag,q in [('19-note','Show the fingering for A5.'),('20-model','Show the fingering for A on YAS-26.'),('21-instrument','Show the fingering for A on tenor saxophone.')]:
        refused=ask(q,'Stage A',tag);assert refused['plan']==target['plan'] and refused['history']==target['history']
    retract=ask('I do not play a Yamaha YAS-280.','No model was confirmed','21a-retract');assert not retract['fingering_context'] and retract['plan']==target['plan'] and retract['history']==target['history']
    needed=ask('Show the fingering for A.','Which saxophone model','21a2-reconfirm-needed');assert not needed['fingering_context'] and needed['plan']==target['plan']
    confirmed=ask('I play a Yamaha YAS-280.','identified','21a3-reconfirm');assert confirmed['plan']==target['plan']
    restored=ask('Show the fingering for A4.','written A4','21a4-lookup-restored');assert restored['plan']==target['plan'] and restored['history']==target['history']
    select(page,'Instrument','Flute')
    bound=ask('Make it easier.','Simplified','21b-bound-sidebar');assert bound['plan']['player']['key']=='alto' and bound['settings']['instrument']=='Flute'
    boundstaff=ask('Can you show me that note on the staff?','written A4','21c-bound-staff');assert boundstaff['plan']==bound['plan'] and boundstaff['history']==bound['history']
    trumpet=ask('Give me a beginner trumpet lip-slur exercise.','lip-slur partial','22-trumpet')
    assert trumpet['plan']['spec']['trumpet'] and trumpet['plan']['items'][0]['written_midi']==[60,67]*2

    warm=ask('Give me a five-minute alto sax warmup.','warmup','23-ordinary-warmup')
    panel=page.locator('[class*="st-key-music_coach_insight_panel_"]').last
    navigated=[]
    for index in (0,1):
        panel.get_by_role('button',name='Next exercise',exact=True).click()
        panel.get_by_text('Exercise '+str(index+1)+' of',exact=False).first.wait_for(timeout=90000)
        iframe=panel.locator('iframe').first
        iframe.wait_for(state='attached',timeout=45000)
        frame=iframe.element_handle().content_frame()
        expected=warm['plan']['items'][index]['abc']
        frame.wait_for_function('(abc)=>window.__amiActualRenders && window.__amiActualRenders.some(r=>r.abc===abc)',arg=expected,timeout=45000)
        assert frame.locator('.ami-fingering').count()==0
        navigated.append({'index':index,'abc_matches_stored':True})
    (out/'ordinary-navigation.json').write_text(json.dumps(navigated,indent=2),encoding='utf-8')
