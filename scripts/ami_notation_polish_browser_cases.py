"""Native ABCJS beam graph/SVG proofs and actual labelled AMI navigation actions."""
import json,re,time
from pathlib import Path
from music_coach_ami.scale_engine import _abc_beam_within_measure
from music_feature_icons import AMI_ACTION_ICONS
CASES=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/ami_beaming_cases.json').read_text())

def run(page,request,select,out):
    def ask(q,cue,tag):
        r,staff=request(page,q,cue,'notation-'+tag)
        assert r['before_settings']==r['settings'];return r,staff
    def current_frame():
        iframe=page.locator('[class*="st-key-music_coach_insight_panel_"]').last.locator('iframe').first
        return iframe,iframe.element_handle().content_frame()
    def native_graph(frame,root_id,tune):
        return frame.evaluate(r"""({id,index})=>{
            const r=window.__amiActualRenders[index],all=[];
            for(const tune of r.tunes)for(const line of tune.lines||[])for(const staff of line.staff||[])for(const voice of staff.voices||[])for(const e of voice)if(e.el_type==='note')all.push(e);
            const pitched=all.filter(e=>e.pitches&&e.pitches.length),beams=[...new Set(pitched.map(e=>e.abselem&&e.abselem.beam).filter(Boolean))];
            const root=document.getElementById(id);
            return {events:all.map(e=>({duration:e.duration,rest:e.rest&&e.rest.type,pitches:(e.pitches||[]).map(p=>({pitch:p.pitch,accidental:p.accidental,startSlur:p.startSlur,endSlur:p.endSlur})),decoration:e.decoration,startSlur:e.startSlur,endSlur:e.endSlur})),groups:beams.map(b=>b.elems.map(e=>pitched.indexOf(e.abcelem)).filter(i=>i>=0)),levels:beams.map(b=>b.beams.length),svgBeams:root.querySelectorAll('.abcjs-beam-elem').length,subpaths:[...root.querySelectorAll('.abcjs-beam-elem')].map(e=>(e.getAttribute('d').match(/M/g)||[]).length),slurs:root.querySelectorAll('.abcjs-slur').length,width:root.getBoundingClientRect().width,scrollWidth:root.scrollWidth,svgWidth:root.querySelector('svg').getBoundingClientRect().width};
        }""",{'id':root_id,'index':tune})
    def production_beams(tag,require_slur=False):
        iframe,f=current_frame();data=f.evaluate(r"""()=>{
          const out=[];
          for(const r of window.__amiActualRenders) for(const t of r.tunes) for(const l of t.lines||[]) for(const staff of l.staff||[]) for(const v of staff.voices||[]){
            const notes=v.filter(e=>e.el_type==='note'&&e.pitches&&e.pitches.length);
            const beams=[...new Set(notes.map(e=>e.abselem&&e.abselem.beam).filter(Boolean))];
            out.push({notes:notes.map(e=>({duration:e.duration,pitches:e.pitches.map(p=>p.pitch)})),groups:beams.map(b=>b.elems.length),levels:beams.map(b=>b.beams.length)});
          }
          return out;
        }""")
        assert any(d['groups'] for d in data),(tag,data)
        geometry_js=r"""()=>{
          const paths=[...document.querySelectorAll('.ami-score-scroll svg path')].filter(p=>!p.hasAttribute('data-name'));
          return {beams:paths.filter(p=>p.getAttribute('class')===''&&/^M[-\d. ]+ L/.test(p.getAttribute('d')||'')&&/z/i.test(p.getAttribute('d')||'')).length,
                  curves:document.querySelectorAll('.ami-score-scroll svg path[data-name="slur"]').length};
        }"""
        geometry=f.evaluate(geometry_js)
        assert geometry['beams']==sum(len(d['groups']) for d in data),(tag,geometry,data)
        if require_slur:assert geometry['curves']>0
        data.append({'actual_svg_geometry':geometry})
        (out/(tag+'-native-beams.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
        for width,height,label in [(1440,1000,'desktop'),(390,844,'mobile')]:
            page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(400)
            iframe,f=current_frame();assert f.evaluate(geometry_js)==geometry
            observed=f.evaluate("()=>({width:innerWidth,body:document.body.scrollWidth,regions:[...document.querySelectorAll('.ami-score-scroll')].map(e=>({width:e.getBoundingClientRect().width,client:e.clientWidth,scroll:e.scrollWidth})),svgWidths:[...document.querySelectorAll('.ami-score-scroll svg')].map(e=>e.getBoundingClientRect().width)})")
            assert observed['body']<=observed['width']+1 and all(v['width']<=observed['width']+1 for v in observed['regions'])
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            (out/(tag+'-'+label+'-layout.json')).write_text(json.dumps(observed,indent=2),encoding='utf-8')
            iframe.screenshot(path=str(out/(tag+'-'+label+'-actual-score.png')))
        page.set_viewport_size({'width':1440,'height':1000})
    select(page,'Instrument','Flute');select(page,'Level','Advanced')
    scale,_=ask('Give me an advanced flute scale exercise in C using eighth notes.','Concert key C','scale-eighths');production_beams('scale-eighths')
    # The proof uses the actual app iframe and the same pinned ABCJS renderer.
    # Before is the previous writer's literal space join, after is its corrected
    # shared serialization. Both are rendered and their native events compared.
    iframe,f=current_frame();render_count=f.evaluate('window.__amiActualRenders.length')
    for width,height,label in [(1440,1100,'desktop'),(390,1100,'mobile')]:
        page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(500)
        for case in CASES:
            body=_abc_beam_within_measure(case['tokens'],case['meter'],'1/4')+' |'
            before=' '.join(case['tokens'])+' |';header=f"X:1\nM:{case['meter']}\nL:1/4\nK:C\n"
            indices=f.evaluate(r"""({before,after})=>{
              let root=document.getElementById('ami-beam-proof');if(root)root.remove();root=document.createElement('section');root.id='ami-beam-proof';root.style.cssText='background:white;color:#111;padding:8px;font:15px Arial;max-width:100%;box-sizing:border-box';root.innerHTML='<h3 style="margin:8px 0">Before: legacy spacing</h3><div id="beam-before"></div><h3 style="margin:8px 0">After: meter-aware beams</h3><div id="beam-after"></div>';document.body.append(root);
              const opts={responsive:'resize',staffwidth:Math.min(700,innerWidth-32),add_classes:true,paddingbottom:8};let a=window.__amiActualRenders.length;ABCJS.renderAbc('beam-before',before,opts);let b=window.__amiActualRenders.length;ABCJS.renderAbc('beam-after',after,opts);return [a,b];
            }""",{'before':header+before,'after':header+body})
            old=native_graph(f,'beam-before',indices[0]);new=native_graph(f,'beam-after',indices[1])
            assert old['events']==new['events'],case['id']
            assert new['groups']==case['beam_groups'] and new['levels']==case['beam_levels'],(case['id'],new)
            assert new['svgBeams']==len(case['beam_groups']) and new['subpaths']==case['beam_levels']
            assert old['svgBeams']==0 and old['groups']==[]
            if case.get('slurs'):assert new['slurs']>=case['slurs'] and old['slurs']>=case['slurs']
            assert new['svgWidth']<=new['width']+1 and new['scrollWidth']<=new['width']+1
            tag=label+'-'+case['id'];(out/(tag+'.json')).write_text(json.dumps({'before':old,'after':new,'abc_before':header+before,'abc_after':header+body},indent=2),encoding='utf-8')
            iframe.evaluate('(e,h)=>{e.style.height=h+"px";e.height=h}',f.evaluate('document.body.scrollHeight')+20)
            proof=f.locator('#ami-beam-proof');proof.scroll_into_view_if_needed();proof.screenshot(path=str(out/(tag+'-raw-before-after.png')))
            native_html=proof.evaluate('(e)=>e.outerHTML');capture=page.context.new_page();capture.set_viewport_size({'width':int(proof.bounding_box()['width']),'height':1000});capture.set_content('<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0;background:white">'+native_html+'</body></html>');capture.locator('#ami-beam-proof').screenshot(path=str(out/(tag+'-before-after.png')));capture.close()
            f.evaluate('document.getElementById("ami-beam-proof").remove();window.__amiActualRenders.length='+str(render_count))
    page.set_viewport_size({'width':1440,'height':1000})
    arp,_=ask('Give me an advanced flute arpeggio exercise in C using eighth notes.','Concert key C','arpeggio-eighths');production_beams('arpeggio-eighths')
    sax,_=ask('Give me an advanced alto sax finger-buster with accents.','finger coordination','sax-sixteenths');production_beams('sax-sixteenths')
    slurred,_=ask('Slur every two notes.','Updated only','slurred-sixteenths');production_beams('slurred-sixteenths',True)
    # Actual adaptive warmup and button interactions, including history preservation.
    select(page,'Instrument','Saxophone');select(page,'Level','Intermediate');select(page,'Focus','Articulation')
    warm,_=ask('Give me a five-minute warmup for alto saxophone.','warmup','warmup-navigation');production_beams('warmup-articulation')
    def button(tag):return page.locator('[class*="st-key-ami_warmup_'+tag+'_"] button').last
    from __main__ import RUNS,finish,idle
    def settle():
        last=RUNS['finished'];stable=time.monotonic();deadline=stable+90
        while time.monotonic()<deadline:
            if RUNS['running'] or RUNS['finished']!=last:last=RUNS['finished'];stable=time.monotonic()
            elif time.monotonic()-stable>.5:idle(page);return
            page.wait_for_timeout(50)
        raise AssertionError('Navigation did not settle')
    def click_nav(tag):
        settle();before=RUNS['finished'];button(tag).click(timeout=90000);finish(page,before,'warmup navigation '+tag);settle()
    click_nav('next');click_nav('next')
    for width,height,label in [(1440,1000,'desktop'),(390,844,'mobile')]:
        page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(600)
        observed=[]
        for tag,text in [('prev','Previous exercise'),('next','Next exercise'),('all','Whole warmup')]:
            b=button(tag);b.scroll_into_view_if_needed();assert text in b.inner_text() and AMI_ACTION_ICONS[tag] in b.inner_text()
            observed.append(b.evaluate('(e)=>({text:e.innerText,width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height,scrollWidth:e.scrollWidth,clientWidth:e.clientWidth})'))
        assert all(v['scrollWidth']<=v['clientWidth']+1 for v in observed)
        assert max(v['height'] for v in observed)-min(v['height'] for v in observed)<3
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        (out/(label+'-navigation.json')).write_text(json.dumps(observed,indent=2),encoding='utf-8');button('next').locator('xpath=ancestor::*[@data-testid="stHorizontalBlock"][1]').screenshot(path=str(out/(label+'-navigation.png')))
    click_nav('prev');click_nav('all');page.set_viewport_size({'width':1440,'height':1000})
    why,_=ask('Explain why these notes work.','Why','navigation-readonly');assert why['plan']==warm['plan'] and why['history']==warm['history']
    dismiss=page.locator('[class*="st-key-ami_insight_dismiss_"] button').last;assert 'Dismiss insight' in dismiss.inner_text() and AMI_ACTION_ICONS['dismiss'] in dismiss.inner_text();dismiss.screenshot(path=str(out/'dismiss-button.png'));before=RUNS['finished'];dismiss.click();finish(page,before,'dismiss insight');settle();dismiss.wait_for(state='hidden',timeout=90000)
    after,_=ask('Explain why these notes work in the stored warmup.','Why','after-dismiss');assert after['plan']==warm['plan'] and after['history']==warm['history']
    import walk_guitar_shape_key as catalog_ui,walk_creative_backing_matrix as existing_ui
    catalog_ui.OUT=out/'catalog';existing_ui.OUT=out/'catalog';catalog_ui.OUT.mkdir(exist_ok=True)
    assert catalog_ui.pick_song(page,[],'Satin Doll','Jazz');page.locator('.st-key-studio_quick_nav_btn_practice button:visible').first.click();page.get_by_test_id('stMainBlockContainer').get_by_role('textbox',name='Question',exact=True).wait_for(timeout=90000)
    jazz,_=ask('Give me an advanced soprano sax jazz anticipation exercise in sixteenth notes over Satin Doll.','Jazz untied anticipations','jazz-sixteenths');production_beams('jazz-sixteenths')
