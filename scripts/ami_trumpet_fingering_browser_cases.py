"""Real-app independent staff/valve/partial, desktop/mobile and conversation gate."""
import json
from pathlib import Path
O=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/ytr2330_fingering_oracle.json').read_text(encoding='utf-8'))
NOTES={n['id']:{**n,'valve':valve} for valve,s in O['sets'].items() for n in s['notes']}
POSITIONS={'Bb3':-1,'B3':-1,'C4':0,'F4':3,'F#4':3,'G4':4,'Bb4':6,'B4':6,'C5':7,'G5':11}

def run(page,request,select,out):
    select(page,'Instrument','Saxophone')
    def ask(q,cue,tag):
        r,staff=request(page,q,cue,'trumpet-fingering-'+tag)
        assert r['before_settings']==r['settings']
        if r['response']['diagnostics'].get('fingering_lookup'):
            ids=[x['id'] for x in r['response']['diagnostics']['fingering_instruction']]
            notes=[n['pitches'][0] for row in staff for n in row['notes'] if n.get('pitches')]
            assert [n['pitch'] for n in notes]==[POSITIONS[n] for n in ids]
            for note,observed in zip(ids,notes):
                expected='flat' if 'b' in note else 'sharp' if '#' in note else None
                assert observed.get('accidental')==expected,(note,observed)
        return r
    def visual(note,tag):
        iframe=page.locator('[class*="st-key-music_coach_insight_panel_"]').last.locator('iframe').first
        f=iframe.element_handle().content_frame();figure=f.locator('.ami-trumpet-fingering[data-record="'+note+'"]')
        figure.wait_for();figure.scroll_into_view_if_needed();figure.focus()
        assert figure.evaluate('(e)=>document.activeElement===e')
        observed=figure.evaluate("""e=>({label:e.getAttribute('aria-label'),desc:document.getElementById(e.getAttribute('aria-describedby')).textContent,partial:e.querySelector('svg').dataset.partial,svg:e.querySelector('svg').getBoundingClientRect().toJSON(),width:innerWidth,body:document.body.scrollWidth,valves:[...e.querySelectorAll('[data-valve]')].map(k=>({id:k.dataset.valve,pressed:k.dataset.pressed,fill:getComputedStyle(k.querySelector('circle')).fill})),fonts:[...e.querySelectorAll('svg text')].map(t=>t.getBoundingClientRect().height)})""")
        assert observed['body']<=observed['width']+1 and observed['svg']['width']>=280
        assert observed['svg']['right']<=observed['width']+1 and min(observed['fonts'])>=12 and len(observed['valves'])==3
        assert observed['partial']==str(NOTES[note]['partial']) and note in observed['label']
        for v in observed['valves']:
            pressed=O['valve_states'][NOTES[note]['valve']][v['id']]
            assert v['pressed']==str(pressed).lower() and v['fill']==('rgb(23, 78, 166)' if pressed else 'rgb(255, 255, 255)')
        assert 'Press:' in observed['desc'] and 'Release:' in observed['desc'] and 'not independently teacher-reviewed or physically tested' in figure.inner_text()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        figure.screenshot(path=str(out/(tag+'-diagram.png')));iframe.screenshot(path=str(out/(tag+'-staff-diagram.png')))
        (out/(tag+'-visual.json')).write_text(json.dumps(observed,indent=2),encoding='utf-8')
        figure.press('Tab');assert f.evaluate("document.activeElement.tagName==='A'")
    missing=ask('Show the fingering for C4 on Bb trumpet.','Which trumpet model','model-needed');assert not missing['plan']
    ask('I play a Yamaha YTR-2330.','identified','model')
    for note in NOTES:
        page.set_viewport_size({'width':1440,'height':1000})
        r=ask('Show the fingering for '+note+' on Bb trumpet.','written '+note,'lookup-'+note);assert not r['plan']
        visual(note,'desktop-'+note)
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(700);visual(note,'mobile-'+note)
    page.set_viewport_size({'width':1440,'height':1000})
    ask('Show me the notes of the open harmonic series.','Supported harmonic-series slice','open-series')
    for note in ('C4','G4','C5'):visual(note,'same-valves-'+note)
    ambiguous=ask("What's the fingering for C on B-flat trumpet?",'Ambiguous register','ambiguous-C')
    assert [r['id'] for r in ambiguous['response']['diagnostics']['fingering_instruction']]==['C4','C5']
    base=ask('Give me an exercise moving between those notes.','Adjacent verified partial path','handoff');assert base['plan']['items'][0]['written_midi']==[60,67,72]
    pair=ask('Start with C and move up to G.','Revised verified lip slur','start-C-G');assert pair['plan']['items'][0]['written_midi']==[60,67]
    added=ask('Now add the next supported partial.','Revised verified lip slur','add-partial');assert added['plan']['items'][0]['written_midi']==[60,67,72]
    refused=ask('Add the next supported partial.','beyond 4','no-partial-5');assert refused['plan']==added['plan'] and refused['history']==added['history']
    slow=ask('Make it slower.','Revised verified lip slur','slower');assert slow['plan']['spec']['bpm']==40
    repeated=ask('Repeat the pattern.','Revised verified lip slur','repeat');assert repeated['plan']['spec']['reps']==2
    shown=ask('Show me the valves for each note.','Read-only explanation','show-each');assert shown['plan']==repeated['plan'] and shown['history']==repeated['history']
    explained=ask('Explain what changes when the valves stay the same.','tube length','explain');assert explained['plan']==repeated['plan'] and explained['history']==repeated['history']
    undo=ask('Undo.','Restored the exact stored version','undo');assert undo['plan']==slow['plan']
    redo=ask('Redo.','Restored the exact stored version','redo');assert redo['plan']==repeated['plan']
    easy=ask('Make it easier.','Revised verified lip slur','easier');assert easy['plan']['items'][0]['written_midi']==[60,67]
    for tag,q in [('combo','Show valves 1+2.'),('high','Show the fingering for C6.'),('model','Show the fingering for G on YTR-8335.')]:
        r=ask(q,'No exercise','negative-'+tag);assert r['plan']==easy['plan'] and r['history']==easy['history']
    ask('Show the fingering for Bb3.','written Bb3','valve1-lookup')
    v1=ask('Give me an exercise moving between those notes.','Adjacent verified partial path','valve1-handoff');assert v1['plan']['items'][0]['written_midi']==[58,65]
    ask('Show the fingering for B3.','written B3','valve2-lookup')
    v2=ask('Give me an exercise moving between those notes.','Adjacent verified partial path','valve2-handoff');assert v2['plan']['items'][0]['written_midi']==[59,66]
    sax=ask('Show the fingering for G5 on Yamaha YAS-280.','written G5','preserve-sax');assert sax['plan']==v2['plan'] and not sax['trumpet_fingering_context']
    ordinary=ask('Give me a beginner trumpet lip-slur exercise.','lip-slur partial','ordinary-owner');assert ordinary['plan']['spec']['trumpet'] and not ordinary['plan']['spec'].get('trumpet_fingering')
