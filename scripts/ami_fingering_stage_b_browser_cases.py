"""Real-app Stage B source-oracle, native staff and responsive comparison checks."""
import json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'tests/fixtures'
O=json.loads((P/'yas280_basic_fingering_oracle.json').read_text())['notes']
O.update(json.loads((P/'yas280_stage_b_oracle.json').read_text())['notes'])
POSITIONS={'D4':1,'E4':2,'F4':3,'G4':4,'A4':5,'B4':6,'C5':7,'D5':8,'E5':9,'F5':10,'G5':11,'A5':12}

def run(page,request,select,out,probe=False):
    select(page,'Instrument','Saxophone')
    def ask(q,cue,tag):
        r,staff=request(page,q,cue,'fingering-b-'+tag)
        assert r['before_settings']==r['settings']
        if r['response']['diagnostics'].get('fingering_lookup'):
            ids=[x['id'] for x in r['response']['diagnostics']['fingering_instruction']]
            actual=[n['pitches'][0]['pitch'] for row in staff for n in row['notes'] if n.get('pitches')]
            assert actual==[POSITIONS[n] for n in ids],(ids,actual)
        return r
    def visual(note,tag):
        panel=page.locator('[class*="st-key-music_coach_insight_panel_"]').last
        iframe=panel.locator('iframe').first;f=iframe.element_handle().content_frame()
        figure=f.locator('.ami-fingering[data-record="'+note+'"]');figure.wait_for()
        figure.scroll_into_view_if_needed();figure.focus();assert figure.evaluate('(e)=>document.activeElement===e')
        assert 'not independently teacher-reviewed' in figure.inner_text()
        observed=figure.evaluate("""e=>({label:e.getAttribute('aria-label'),desc:document.getElementById(e.getAttribute('aria-describedby')).textContent,svg:e.querySelector('svg').getBoundingClientRect().toJSON(),width:innerWidth,body:document.body.scrollWidth,keys:[...e.querySelectorAll('[data-key]')].map(k=>({id:k.dataset.key,pressed:k.dataset.pressed,fill:getComputedStyle(k.querySelector('circle')).fill})),fonts:[...e.querySelectorAll('svg text')].map(t=>t.getBoundingClientRect().height)})""")
        assert observed['body']<=observed['width']+1 and observed['svg']['width']>=280
        assert observed['svg']['right']<=observed['width']+1 and min(observed['fonts'])>=12 and len(observed['keys'])==7
        for key in observed['keys']:
            pressed=key['id'] in O[note]['pressed']
            assert key['pressed']==str(pressed).lower() and key['fill']==('rgb(23, 78, 166)' if pressed else 'rgb(255, 255, 255)')
        assert note in observed['label'] and 'Press:' in observed['desc'] and 'Release:' in observed['desc']
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        figure.screenshot(path=str(out/(tag+'-diagram.png')));iframe.screenshot(path=str(out/(tag+'-staff-diagram.png')))
        (out/(tag+'-visual.json')).write_text(json.dumps(observed,indent=2),encoding='utf-8')
        figure.press('Tab');assert f.evaluate("document.activeElement.tagName==='A'")
    if probe:
        generic=ask('Give me a beginner alto sax exercise in octaves.','octaves','final-generic-owner')
        assert generic['plan']['spec']['sax']['interval']=='octaves'
        assert not generic['fingering_context']
    if not probe:
        ask('Give me an octave exercise using G on alto sax.','Which saxophone model','01-model-needed')
    ask('I play a Yamaha YAS-280.','identified','02-model')
    if probe:
        ask('Show me how to go from low G to high G on alto sax.','12 semitones','final-pair')
        for width,height,label in ((1440,1000,'desktop'),(390,844,'mobile')):
            page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(900)
            for note in ('G4','G5'):visual(note,'final-'+label+'-'+note)
        page.set_viewport_size({'width':1440,'height':1000})
        base=ask('Give me a short exercise using these two notes.','Verified octave exercise','final-handoff')
        assert base['plan']['items'][0]['written_midi']==[67,79]
        slow=ask('Make the transition slower.','Revised verified transition','final-slower')
        assert slow['plan']['spec']['bpm']==50
        undo=ask('Undo.','Restored the exact stored version','final-undo');assert undo['plan']==base['plan']
        redo=ask('Redo.','Restored the exact stored version','final-redo');assert redo['plan']==slow['plan']
        return
    for note in ('D4','E4','F4','C5','D5','E5','F5','G5','A5'):
        page.set_viewport_size({'width':1440,'height':1000})
        r=ask('Show the fingering for '+note+'.','written '+note,'lookup-'+note)
        assert not r['plan']
        visual(note,'desktop-'+note)
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(900);visual(note,'mobile-'+note)
    for letter in ('G','A'):
        page.set_viewport_size({'width':1440,'height':1000})
        ask('Show me how to go from low '+letter+' to high '+letter+' on alto sax.','12 semitones','pair-'+letter)
        for note in (letter+'4',letter+'5'):visual(note,'desktop-pair-'+note)
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(900)
        for note in (letter+'4',letter+'5'):visual(note,'mobile-pair-'+note)
    page.set_viewport_size({'width':1440,'height':1000})
    ask("What's the difference between the two G fingerings?",'G4 / G5','difference-G')
    base=ask('Give me a short exercise using these two notes.','Verified octave exercise','exercise')
    assert base['plan']['items'][0]['written_midi']==[67,79]
    slow=ask('Make the transition slower.','Revised verified transition','slower');assert slow['plan']['spec']['bpm']==50
    repeated=ask('Repeat the octave jump four times.','Revised verified transition','repeat');assert repeated['plan']['spec']['reps']==4
    hard=ask('Give me a harder register-transition exercise.','Revised verified transition','harder');assert hard['plan']['items'][0]['written_midi']==[67,79,67,79]
    desc=ask('Make it descending.','Revised verified transition','descending');assert desc['plan']['items'][0]['written_midi']==[79,67,79,67]
    keys=ask('Explain which keys change.','Octave thumb: release','key-changes');assert keys['plan']==desc['plan'] and keys['history']==desc['history']
    undo=ask('Undo.','Restored the exact stored version','undo');assert undo['plan']==hard['plan']
    redo=ask('Redo.','Restored the exact stored version','redo');assert redo['plan']==desc['plan']
    easy=ask('Make it easier.','Revised verified transition','easier');assert easy['plan']['items'][0]['written_midi']==[79,67] and easy['plan']['spec']['bpm']==50 and easy['plan']['spec']['reps']==4
    ask('Make it ascending.','Revised verified transition','ascending')
    lead=ask('Add a few notes leading into high G.','Revised verified transition','lead');assert lead['plan']['items'][0]['written_midi']==[67,76,77,79]
    ladder=ask('Start with low notes and gradually move higher.','Revised verified transition','gradual');assert ladder['plan']['items'][0]['written_midi']==[62,64,65,67,69,71,72,74]
    for tag,q,cue in [('unsupported','Show the fingering for B5.','unsupported'),('ambiguous','Show the fingering for C.','unsupported'),('model','Show the fingering for G on YAS-26.','outside'),('special','Show an alternate fingering for G5.','instruction is not supported'),('non-octave','Compare the fingerings for G4 and A5.','Choose one verified')]:
        refused=ask(q,cue,'negative-'+tag);assert refused['plan']==ladder['plan'] and refused['history']==ladder['history']
    compared=ask('Show the fingerings for G4 and G5.','12 semitones','readonly-G')
    assert compared['plan']==ladder['plan'] and compared['history']==ladder['history']
    select(page,'Instrument','Flute')
    staff=ask('Show these two notes on the staff.','G4 / G5','bound-staff');assert staff['plan']==ladder['plan'] and staff['settings']['instrument']=='Flute'
    actual=ask('Explain which keys change in the exercise.','D4 to E4','actual-exercise');assert actual['plan']==ladder['plan'] and actual['history']==ladder['history']
    trumpet=ask('Give me a beginner trumpet lip-slur exercise.','lip-slur partial','ordinary-trumpet');assert trumpet['plan']['spec']['trumpet']
