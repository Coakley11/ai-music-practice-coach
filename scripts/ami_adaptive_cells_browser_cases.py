"""Real application: exact cells, independent native pitches/timing, beams and history."""
import copy,json
from fractions import Fraction


def run(page,request,select,out):
    select(page,'Instrument','Flute');select(page,'Level','Intermediate')
    observations=[]
    def panel():return page.locator('[class*="st-key-music_coach_insight_panel_"]').last
    def native(record,tag):
        iframe=panel().locator('iframe').first;frame=iframe.element_handle().content_frame()
        actual=frame.evaluate(r'''()=>{
          const renders=window.__amiActualRenders.slice(),notes=[],groups=[],levels=[];let warnings=0;
          for(const r of renders)for(const t of r.tunes){
            warnings+=(t.warnings||[]).length;
            for(const tr of t.setUpAudio().tracks)for(const e of tr)if(e.cmd==='note')notes.push([e.pitch,e.start,e.duration]);
            for(const line of t.lines||[])for(const staff of line.staff||[])for(const voice of staff.voices||[]){
              const beams=[...new Set(voice.map(e=>e.abselem&&e.abselem.beam).filter(Boolean))];
              for(const b of beams){groups.push(b.elems.length);levels.push(b.beams.length)}
            }
          }
          const host=document.createElement('div');document.body.appendChild(host);
          let calibration;
          try{
            const t=ABCJS.renderAbc(host,'X:1\nM:4/4\nL:1/4\nK:C\nC D2 z |')[0];
            calibration=t.setUpAudio().tracks.flat().filter(e=>e.cmd==='note').map(e=>[e.pitch,e.start,e.duration]);
          }finally{host.remove();window.__amiActualRenders=renders}
          return {notes,groups,levels,warnings,calibration,slurs:document.querySelectorAll('.ami-score-scroll svg path[data-name="slur"]').length};
        }''')
        plan=record['plan'];shown=plan.get('original',plan) if record['history'].get('view',{}).get('mode')=='original' else plan
        row=shown['items'][0];unit=Fraction(2)/Fraction(str(actual['calibration'][1][2])).limit_denominator(10000)
        have=[(int(m),Fraction(str(t)).limit_denominator(10000)*unit,Fraction(str(d)).limit_denominator(10000)*unit) for m,t,d in actual['notes']]
        durations={'whole':4,'half':2,'quarter':1,'eighth':Fraction(1,2),'sixteenth':Fraction(1,4)}
        expected=[(m,Fraction(str((r['bar']-1)*4+r['beat']-1)),Fraction(durations[r['duration']])) for m,r in zip(row['written_midi'],[v for v in row['note_name_rows'] if v['name']!='rest'])]
        assert have==expected,(tag,have,expected)
        assert actual['warnings']==0,(tag,actual)
        if shown['spec'].get('slur') and shown['spec']['count']>1:assert actual['slurs']>=len(row['cells']),(tag,actual['slurs'])
        if shown['spec']['rhythm'] in ('eighth','sixteenth') and shown['spec']['family']=='lick' and shown['spec']['count']>=4:
            limit=2 if shown['spec']['rhythm']=='eighth' else 4
            assert actual['groups'] and max(actual['groups'])<=limit,(tag,actual['groups'])
            if limit==4:assert max(actual['levels'])>=2
        observations.append({'tag':tag,'written_pitches':[m for m,t,d in have],'quarter_onsets':[str(t) for m,t,d in have],'quarter_durations':[str(d) for m,t,d in have],'beam_groups':actual['groups'],'beam_levels':actual['levels'],'warnings':0,'slurs':actual['slurs']})
        (out/'native-acceptance.json').write_text(json.dumps(observations,indent=2),encoding='utf-8')
    def ask(q,tag,cue='Exact cell study'):
        r,staff=request(page,q,cue,'adaptive-'+tag)
        assert r['before_settings']==r['settings']
        native(r,tag);return r
    def images(tag):
        for width,height,label in [(1440,1000,'desktop'),(390,844,'mobile')]:
            page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(350)
            panel().locator('iframe').first.scroll_into_view_if_needed()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            page.screenshot(path=str(out/(tag+'-'+label+'.png')))
    original=ask('Give me a four-note lick in G major.','four')
    assert original['plan']['items'][0]['written_midi']==[67,69,71,74]
    assert not panel().get_by_role('checkbox',name='Show note names',exact=True).is_checked()
    images('four-note-cell')
    harder=ask('Make it harder.','harder');assert len(harder['plan']['items'][0]['written_midi'])==4
    ask('Use eighth notes.','eighths','already stored')
    ask('Make it sixteenth notes.','sixteenths')
    ask('Add slurs.','slurs')
    diatonic=ask('Move the lick through all seven degrees.','diatonic')
    assert len(diatonic['plan']['items'][0]['cells'])==7
    images('diatonic-cells')
    ask('Now make the sequence descending.','diatonic-descending')
    ask('Do the same exercise in thirds.','thirds')
    keys=ask('Now transpose the original lick through twelve keys, ascending.','twelve-keys')
    assert len(keys['plan']['items'][0]['cells'])==12 and keys['plan']['spec']['offsets']==[0,2,4,7]
    images('twelve-key-cell')
    descending=ask('Make the sequence descending.','keys-descending')
    reviewed=ask('Show me the first lick again.','first-lick','Read-only first-lick')
    assert reviewed['plan']==descending['plan'] and reviewed['response']['notation_abc']==original['response']['notation_abc']
    explained=ask('Explain the pattern.','explain','Read-only explanation')
    assert explained['plan']==descending['plan'] and explained['history']==reviewed['history']
    undo=ask('Undo.','undo','Restored the exact stored version');redo=ask('Redo.','redo','Restored the exact stored version')
    assert undo['plan']==keys['plan'] and redo['plan']==descending['plan']
    explicit=ask('Play the same lick in G, then G-sharp, A, B-flat and B.','explicit-keys')
    assert [c['concert_key'] for c in explicit['plan']['items'][0]['cells']]==['G','G#','A','Bb','B']
    whole=ask('Move it by whole steps.','whole-steps');assert len(whole['plan']['items'][0]['cells'])==6
    circle=ask('Move it around the circle of fourths.','fourths-cycle');assert len(circle['plan']['items'][0]['cells'])==12
    jazz=ask('Give me a five-note jazz lick in G major.','five-jazz');assert len(jazz['plan']['items'][0]['written_midi'])==5
    images('five-note-jazz')
    blues=ask('Give me a six-note blues lick in G major.','six-blues');assert len(blues['plan']['items'][0]['written_midi'])==6
    images('six-note-blues')
    ask('Give me a descending six-note lick in G major.','six-descending')
    sixths=ask('Give me sixths in G major.','sixths');assert max(sixths['plan']['items'][0]['written_midi'])<=91
    images('range-checked-sixths')
    ask('Give me ascending fourths.','ascending-fourths')
    ask('Give me descending fifths.','descending-fifths')
    ask('Give me octaves.','octaves')
    select(page,'Level','Beginner')
    beginner=ask('Give me a four-note lick in G major.','beginner')
    assert panel().get_by_role('checkbox',name='Show note names',exact=True).is_checked()
    refused=ask('Move the lick through the whole major scale and back down.','range-refusal','cannot make')
    assert refused['plan']==beginner['plan'] and refused['history']==beginner['history']
    shown=ask('Show me the note names.','show-names','Written note names')
    hidden=ask('Hide the note names.','hide-names','Note names are hidden')
    assert shown['plan']==hidden['plan']==beginner['plan'] and shown['history']==hidden['history']
    select(page,'Instrument','Saxophone');select(page,'Level','Advanced')
    alto=ask('Give me a four-note lick for alto sax in G major.','alto-four')
    assert alto['plan']['player']['offset']==9
    alto_keys=ask('Transpose this lick through twelve keys.','alto-twelve')
    assert all(w-9==c for w,c in zip(alto_keys['plan']['items'][0]['written_midi'],alto_keys['plan']['items'][0]['sounding_midi']))
    images('alto-twelve-key-cell')
    select(page,'Instrument','Clarinet');select(page,'Level','Intermediate')
    bb=ask('Give me a four-note lick in G major.','clarinet-four')
    assert bb['plan']['player']['offset']==2
    ask('Play the same lick in G, then G-sharp, A, B-flat and B.','clarinet-keys')
    images('clarinet-key-cells')
    (out/'acceptance.json').write_text(json.dumps({'native_requests_verified':len(observations),'exact_counts':[4,5,6],'separate_diatonic_and_key_operations':True,'whole_step_and_fourths':True,'exact_undo_redo':True,'read_only_first_lick_explain_note_names':True,'range_refusal_preserves_plan_history':True,'instrument_offsets':{'alto':9,'clarinet':2,'flute':0},'desktop_mobile_checked':True},indent=2),encoding='utf-8')
