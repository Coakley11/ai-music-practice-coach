"""Real-app independent clarinet control, native staff and register/history acceptance."""
import json
from pathlib import Path
O=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/ycl255_fingering_oracle.json').read_text(encoding='utf-8'))
POSITIONS={'E3':-5,'F3':-4,'G3':-3,'Bb4':6,'B4':6,'C5':7,'D5':8,'G5':11,'G4':4,'C4':0}

def run(page,request,select,out):
    select(page,'Instrument','Saxophone');select(page,'Level','Intermediate')
    def ask(q,cue,tag):
        r,staff=request(page,q,cue,'clarinet-fingering-'+tag)
        assert r['before_settings']==r['settings']
        records=r['response']['diagnostics'].get('fingering_instruction',[])
        if r['response']['diagnostics'].get('fingering_lookup') and records:
            ids=[x['id'] for x in records];actual=[n['pitches'][0] for row in staff for n in row['notes'] if n.get('pitches')]
            assert [n['pitch'] for n in actual]==[POSITIONS[n] for n in ids]
            for i,(note,observed) in enumerate(zip(ids,actual)):
                accidental='flat' if note=='Bb4' else 'natural' if note=='B4' and i%2==1 and ids[i-1]=='Bb4' else None
                assert observed.get('accidental')==accidental,(ids,observed)
        return r
    def visual(note,tag):
        iframe=page.locator('[class*="st-key-music_coach_insight_panel_"]').last.locator('iframe').first;f=iframe.element_handle().content_frame()
        figure=f.locator('.ami-clarinet-fingering[data-record="'+note+'"]');figure.wait_for();figure.scroll_into_view_if_needed();figure.focus()
        assert figure.evaluate('(e)=>document.activeElement===e')
        observed=figure.evaluate("""e=>({label:e.getAttribute('aria-label'),desc:document.getElementById(e.getAttribute('aria-describedby')).textContent,svg:e.querySelector('svg').getBoundingClientRect().toJSON(),width:innerWidth,body:document.body.scrollWidth,holes:[...e.querySelectorAll('[data-hole]')].map(k=>({id:k.dataset.hole,state:k.dataset.covered,fill:getComputedStyle(k.querySelector('circle')).fill})),keys:[...e.querySelectorAll('[data-key]')].map(k=>({id:k.dataset.key,state:k.dataset.pressed,fill:getComputedStyle(k.querySelector('rect')).fill})),fonts:[...e.querySelectorAll('svg text')].map(t=>t.getBoundingClientRect().height)})""")
        assert observed['body']<=observed['width']+1 and observed['svg']['width']>=280 and observed['svg']['right']<=observed['width']+1
        assert min(observed['fonts'])>=12 and len(observed['holes'])==7 and len(observed['keys'])==4
        for kind,field in [('holes','covered'),('keys','pressed')]:
            for c in observed[kind]:
                state=c['id'] in O['notes'][note][field]
                assert c['state']==str(state).lower() and c['fill']==('rgb(23, 78, 166)' if state else 'rgb(255, 255, 255)')
        assert note in observed['label'] and all(x in observed['desc'] for x in ('Cover:','Open:','Press:','Release:'))
        assert 'not teacher-reviewed or physically tested' in figure.inner_text()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        figure.screenshot(path=str(out/(tag+'-diagram.png')));iframe.screenshot(path=str(out/(tag+'-staff-diagram.png')))
        (out/(tag+'-visual.json')).write_text(json.dumps(observed,indent=2),encoding='utf-8')
        figure.press('Tab');assert f.evaluate("document.activeElement.tagName==='A'")
    def compare_visual(ids,tag):
        for width,height,label in ((1440,1000,'desktop'),(390,844,'mobile')):
            page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(700)
            for note in ids:visual(note,tag+'-'+label+'-'+note)
        page.set_viewport_size({'width':1440,'height':1000})
    missing=ask('Show the fingering for E3 on Bb clarinet.','Which clarinet model','model-needed');assert not missing['plan']
    ask('I play a Yamaha YCL-255.','identified','model')
    for note in O['notes']:
        page.set_viewport_size({'width':1440,'height':1000})
        r=ask('Show the fingering for '+note+' on Bb clarinet.','written '+note,'lookup-'+note);assert not r['plan']
        visual(note,'desktop-'+note);page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(700);visual(note,'mobile-'+note)
    page.set_viewport_size({'width':1440,'height':1000})
    ask('How do I play B above the clarinet break?','written B4','above-break')
    ask("What's the fingering for low E?",'written E3','low-E')
    for pair in O['pairs']:
        r=ask('Show the fingerings from '+pair[0]+' to '+pair[1]+'.','19 semitones','pair-'+pair[0]);assert not r['plan']
        compare_visual(pair,'twelfth-'+pair[0])
    r=ask('Show the fingerings for Bb4 and B4 across the clarinet break.','register key stays pressed','break-comparison');assert not r['plan']
    compare_visual(['Bb4','B4'],'break')
    ask("What's the fingering for high B?",'ambiguous','high-B')
    ask('How do I use the register key?','19 semitones','register-key')
    ask('How do I move from low E to B in the clarion register?','19 semitones','low-E-clarion-B')
    base=ask('Give me a slow exercise moving between those notes.','Verified source-backed handoff','handoff');assert base['plan']['items'][0]['written_midi']==[52,71]
    repeated=ask('Repeat the transition four times.','Revised verified clarinet transition','repeat');assert repeated['plan']['spec']['reps']==4
    added=ask('Add another verified twelfth pair.','Revised verified clarinet transition','add-pair');assert added['plan']['items'][0]['written_midi']==[52,71,53,72]
    slow=ask('Make it slower.','Revised verified clarinet transition','slower');assert slow['plan']['spec']['bpm']==40
    desc=ask('Make it descending.','Revised verified clarinet transition','descending');assert desc['plan']['items'][0]['written_midi']==[72,53,71,52]
    explained=ask('Explain what my fingers are changing.','Read-only finger changes','explain');assert explained['plan']==desc['plan'] and explained['history']==desc['history']
    undo=ask('Undo.','Restored the exact stored version','undo');assert undo['plan']==slow['plan']
    redo=ask('Redo.','Restored the exact stored version','redo');assert redo['plan']==desc['plan']
    easy=ask('Make it easier.','Revised verified clarinet transition','easier');assert easy['plan']['items'][0]['written_midi']==[71,52]
    br=ask('Give me a short register-break warmup.','Verified source-backed handoff','break-warmup');assert br['plan']['items'][0]['written_midi']==[70,71]
    brdesc=ask('Make the break descending.','Revised verified clarinet transition','break-descending');assert brdesc['plan']['items'][0]['written_midi']==[71,70]
    brwhy=ask('Explain the finger changes in the exercise.','Read-only finger changes','break-explain');assert brwhy['plan']==brdesc['plan'] and brwhy['history']==brdesc['history']
    for tag,q,cue in [('high','Show the fingering for B5.','unsupported'),('model','Show the fingering for G3 on YCL-450.','outside'),('system','Show the fingering for G3 on Oehler clarinet.','outside'),('altissimo','Show altissimo fingerings.','outside')]:
        r=ask(q,cue,'negative-'+tag);assert r['plan']==brdesc['plan'] and r['history']==brdesc['history']
    limited=ask('Give me a Beginner exercise from E3 to B4.','Intermediate','beginner-limit');assert limited['plan']==brdesc['plan'] and limited['history']==brdesc['history']
    beginner=ask('Give me a Beginner exercise from G3 to D5.','Verified source-backed handoff','beginner-pair');assert beginner['plan']['items'][0]['written_midi']==[55,74]
    looked=ask('Show the fingering for D5.','written D5','readonly-other');assert looked['plan']==beginner['plan'] and looked['history']==beginner['history']
    shown=ask('Explain which fingers are pressed.','written D5','readonly-follow');assert shown['plan']==beginner['plan'] and shown['history']==beginner['history']
    sax=ask('Show the fingering for G5 on Yamaha YAS-280.','written G5','sax-owner');assert not sax['clarinet_fingering_context'] and sax['plan']==beginner['plan']
    trumpet=ask('Show the fingering for G4 on Yamaha YTR-2330 Bb trumpet.','written G4','trumpet-owner');assert not trumpet['clarinet_fingering_context']
    tr=ask('Give me an exercise moving between those notes.','Adjacent verified partial path','trumpet-handoff');assert tr['plan']['spec'].get('trumpet_fingering')
    ordinary=ask('Give me a beginner clarinet register-break exercise.','register-break','ordinary-clarinet');assert ordinary['plan']['spec'].get('technique')=='clarinet_break' and not ordinary['plan']['spec'].get('clarinet_fingering')

    changed=ask('I play a Yamaha YCL-450.','outside','changed-model-identity');assert changed['plan']==ordinary['plan'] and changed['history']==ordinary['history']
    assert not changed['clarinet_fingering_context'].get('model') and changed['clarinet_fingering_context']['instrument']=='clarinet'
    clarified=ask('Show the fingering for E3.','Which clarinet model','changed-model-followup');assert clarified['plan']==ordinary['plan'] and clarified['history']==ordinary['history']
    ask('I play a Yamaha YCL-255.','identified','reconfirm-model')
    restored=ask('Show the fingering for E3 on clarinet.','written E3','reconfirmed-lookup');assert restored['plan']==ordinary['plan'] and restored['history']==ordinary['history']

    scale=ask('Give me a beginner clarinet scale exercise in C.','Concert key C','ordinary-keyed-scale');assert scale['plan']['player']['key']=='clarinet' and not scale['plan']['spec'].get('clarinet_fingering')
    limited_arpeggio=ask('Give me a beginner clarinet arpeggio exercise in F.','complete octave does not fit','ordinary-arpeggio-limit');assert limited_arpeggio['plan']==scale['plan'] and limited_arpeggio['history']==scale['history']
    arpeggio=ask('Give me an Advanced clarinet arpeggio exercise in F.','Concert key F','ordinary-keyed-arpeggio');assert arpeggio['plan']['player']['key']=='clarinet' and not arpeggio['plan']['spec'].get('clarinet_fingering')

    bass=ask('Give me a beginner bass fingering exercise.','Bass guitar','bare-bass-owner');assert bass['plan']['player']['key']=='bass' and bass['plan']['spec'].get('bass') and not bass['plan']['spec'].get('clarinet_fingering') and bass['response']['diagnostics'].get('bass_tab_sections')
