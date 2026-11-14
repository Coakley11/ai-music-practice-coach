"""Real-app flute key states and native staff against a manually reviewed source oracle."""
import json
from pathlib import Path
O=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/yfl222_fingering_oracle.json').read_text(encoding='utf-8'))
N={n['id']:n for n in O['notes']}
POSITIONS={'E4':2,'F4':3,'G4':4,'E5':9,'F5':10,'G5':11}

def run(page,request,select,out):
    select(page,'Instrument','Saxophone');select(page,'Level','Intermediate')
    def ask(q,cue,tag):
        r,staff=request(page,q,cue,'flute-fingering-'+tag)
        assert r['before_settings']==r['settings']
        if r['response']['diagnostics'].get('fingering_lookup'):
            ids=[n['id'] for n in r['response']['diagnostics']['fingering_instruction']]
            if all(n in POSITIONS for n in ids) and r['response']['source_solver']=='FluteFingeringInstructor':
                actual=[n['pitches'][0] for row in staff for n in row['notes'] if n.get('pitches')]
                assert [n['pitch'] for n in actual]==[POSITIONS[n] for n in ids]
                assert all(not n.get('accidental') for n in actual)
        return r
    def visual(note,tag):
        iframe=page.locator('[class*="st-key-music_coach_insight_panel_"]').last.locator('iframe').first;f=iframe.element_handle().content_frame()
        figure=f.locator('.ami-flute-fingering[data-record="'+note+'"]');figure.wait_for();figure.scroll_into_view_if_needed();figure.focus()
        assert figure.evaluate('(e)=>document.activeElement===e')
        observed=figure.evaluate("""e=>({label:e.getAttribute('aria-label'),desc:document.getElementById(e.getAttribute('aria-describedby')).textContent,svg:e.querySelector('svg').getBoundingClientRect().toJSON(),width:innerWidth,body:document.body.scrollWidth,keys:[...e.querySelectorAll('[data-key]')].map(k=>({id:k.dataset.key,state:k.dataset.pressed,fill:getComputedStyle(k.querySelector('circle')).fill})),fonts:[...e.querySelectorAll('svg text')].map(t=>t.getBoundingClientRect().height),figures:[...document.querySelectorAll('.ami-flute-fingering')].map(v=>v.getBoundingClientRect().toJSON())})""")
        assert observed['body']<=observed['width']+1 and observed['svg']['width']>=300 and observed['svg']['right']<=observed['width']+1
        assert min(observed['fonts'])>=12 and len(observed['keys'])==15
        for c in observed['keys']:
            state=c['id'] in N[note]['pressed'];assert c['state']==str(state).lower() and c['fill']==('rgb(23, 78, 166)' if state else 'rgb(255, 255, 255)')
        assert all(t in observed['desc'] for t in ('Press:','Release:','no octave key')) and note in observed['label']
        assert 'not teacher-reviewed or physically tested' in figure.inner_text()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        if len(observed['figures'])==2 and page.viewport_size['width']==1440:assert observed['figures'][0]['x']!=observed['figures'][1]['x']
        if len(observed['figures'])==2 and page.viewport_size['width']==390:assert abs(observed['figures'][0]['x']-observed['figures'][1]['x'])<2
        figure.screenshot(path=str(out/(tag+'-diagram.png')));iframe.screenshot(path=str(out/(tag+'-staff-diagram.png')))
        (out/(tag+'-visual.json')).write_text(json.dumps(observed,indent=2),encoding='utf-8')
        figure.press('Tab');assert f.evaluate("document.activeElement.tagName==='A'")
    def compare_visual(pair,tag):
        for width,height,label in ((1440,1000,'desktop'),(390,844,'mobile')):
            page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(700)
            for note in pair:visual(note,tag+'-'+label+'-'+note)
        page.set_viewport_size({'width':1440,'height':1000})
    r=ask('Show the fingering for E4 on flute.','Which flute model','model-needed');assert not r['plan']
    ask('Does the Yamaha YFL-222 have a split-E mechanism?','no split-E','model-question')
    ask('I play a Yamaha YFL-222.','identified','model')
    for note in N:
        page.set_viewport_size({'width':1440,'height':1000});r=ask('Show the fingering for '+note+' on flute.','written '+note,'lookup-'+note);assert not r['plan'];visual(note,'desktop-'+note)
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(700);visual(note,'mobile-'+note)
    page.set_viewport_size({'width':1440,'height':1000})
    ask("What's the fingering for E on flute?",'ambiguous','ambiguous-E')
    ask('Show me how to play low E.','written E4','low-E')
    ask('How do I play E in the higher octave?','written E5','higher-E')
    ask("What's the difference between low and high G?",'12 semitones','low-high-G')
    for pair in O['pairs']:
        r=ask('Show the difference between '+pair[0]+' and '+pair[1]+' on flute.','identical selected key states','compare-'+pair[0]);assert not r['plan'];compare_visual(pair,'octave-'+pair[0])
    ask('How do I move smoothly from E4 to E5?','12 semitones','smooth-E')
    base=ask('Give me a slow exercise that goes between the two registers.','Verified source-backed flute handoff','handoff');assert len(base['plan']['items'])==1 and base['plan']['items'][0]['written_midi']==[64,76]
    repeated=ask('Repeat it four times.','Revised verified flute transition','repeat');assert repeated['plan']['spec']['reps']==4
    slow=ask('Make it slower.','Revised verified flute transition','slower');assert slow['plan']['spec']['bpm']==40
    desc=ask('Now make it descending.','Revised verified flute transition','descending');assert desc['plan']['items'][0]['written_midi']==[76,64]
    why=ask('Explain which fingers change.','Read-only finger changes','explain');assert why['plan']==desc['plan'] and why['history']==desc['history']
    undo=ask('Undo.','Restored the exact stored version','undo');assert undo['plan']==slow['plan']
    redo=ask('Redo.','Restored the exact stored version','redo');assert redo['plan']==desc['plan']
    hard=ask('Make it more challenging.','Revised verified flute transition','harder');assert hard['plan']['spec']['rhythm']=='quarter' and hard['plan']['spec']['bpm']==48
    easy=ask('Make it easier.','Revised verified flute transition','easier');assert easy['plan']['spec']['rhythm']=='half'
    alternate=ask('Alternate between F4 and F5.','Revised verified flute transition','alternate');assert alternate['plan']['items'][0]['written_midi']==[77,65]
    allpairs=ask('Give me a short Intermediate flute warmup with all three verified octave pairs.','Verified source-backed flute handoff','all-pairs');assert len(allpairs['plan']['items'])==1 and allpairs['plan']['items'][0]['written_midi']==[64,76,65,77,67,79]
    for tag,q in [('high','Show the fingering for E6.'),('alternate','Show alternate fingerings.'),('type','Show the fingering for E4 on bass flute.'),('foot','Use a B footjoint for these fingerings.')]:
        r=ask(q,'verified','negative-'+tag);assert r['plan']==allpairs['plan'] and r['history']==allpairs['history']
    limited=ask('Give me a Beginner flute octave exercise using E4 and E5.','Intermediate','beginner-limit');assert limited['plan']==allpairs['plan'] and limited['history']==allpairs['history']
    beginner=ask('Give me a Beginner flute octave exercise using G4 and G5.','Verified source-backed flute handoff','beginner-G');assert beginner['plan']['items'][0]['written_midi']==[67,79]
    looked=ask('Show the fingering for E4.','written E4','readonly-other');assert looked['plan']==beginner['plan'] and looked['history']==beginner['history']
    higher=ask('Show me the higher octave.','written E5','readonly-higher');assert higher['plan']==beginner['plan'] and higher['history']==beginner['history']
    changed=ask('I play a Yamaha YFL-212.','outside','model-change');assert not changed['flute_fingering_context'].get('model') and changed['plan']==beginner['plan'] and changed['history']==beginner['history']
    clarify=ask('Show the fingering for E4.','Which flute model','model-change-follow');assert clarify['plan']==beginner['plan'] and clarify['history']==beginner['history']
    ask('I play a Yamaha YFL-222.','identified','reconfirm-model')
    for tag,q,cue in [('sax','Show the fingering for G5 on Yamaha YAS-280.','written G5'),('trumpet','Show the fingering for G4 on Yamaha YTR-2330 Bb trumpet.','written G4'),('clarinet','Show the fingering for B4 on Yamaha YCL-255.','written B4')]:
        r=ask(q,cue,'owner-'+tag);assert not r['flute_fingering_context'] and r['plan']==beginner['plan'] and r['history']==beginner['history']
    ask('Show the fingering for E4 on Yamaha YFL-222 flute.','written E4','return-flute')
    limited=ask('Give me an Intermediate flute scale exercise in F.','complete octave does not fit','ordinary-range');assert limited['plan']==beginner['plan']
    scale=ask('Give me an Intermediate flute scale exercise in G.','Concert key G','ordinary-scale');assert not scale['plan']['spec'].get('flute_fingering') and scale['plan']['player']['key']=='flute'
    bass=ask('Give me a beginner bass fingering exercise.','Bass guitar','bare-bass');assert bass['plan']['player']['key']=='bass' and bass['response']['diagnostics'].get('bass_tab_sections')
