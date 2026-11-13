"""Real-card geometry and visual evidence, without replacing the renderer."""
import json

def run(page,request,select,out):
    def audit(tag):
        panel=page.locator('[class*="st-key-music_coach_insight_panel_"]').last
        panel.scroll_into_view_if_needed()
        page.evaluate("window.scrollTo(0,window.scrollY)")
        frames=[]
        for iframe in panel.locator('iframe').all():
            frame=iframe.element_handle().content_frame()
            metrics=frame.evaluate("""() => {
                const papers=[...document.querySelectorAll('[id^="coach_abc_paper_"]')];
                return {bassTabs:window.__amiBassTabs||[],width:innerWidth,bodyWidth:document.body.scrollWidth,height:innerHeight,bodyHeight:document.body.scrollHeight,scores:papers.map(p=>{
                    const c=p.closest('.ami-score-scroll'),svgs=[...p.querySelectorAll('svg')];
                    const glyphs=svgs.flatMap(s=>[...s.querySelectorAll('path,text,line')]).map(g=>g.getBoundingClientRect()).filter(r=>r.width||r.height);
                    const texts=[...p.querySelectorAll('svg text')].filter(t=>t.textContent.trim()).map(t=>({text:t.textContent,height:t.getBoundingClientRect().height}));
                    const left=c.getBoundingClientRect().left-c.scrollLeft,top=c.getBoundingClientRect().top-c.scrollTop;
                    return {client:c.clientWidth,width:c.scrollWidth,overflow:getComputedStyle(c).overflowX,tabindex:c.getAttribute('tabindex'),svgCount:svgs.length,
                        glyphMin:Math.min(...glyphs.map(r=>r.left-left)),glyphMax:Math.max(...glyphs.map(r=>r.right-left)),glyphBottom:Math.max(...glyphs.map(r=>r.bottom-top)),height:c.scrollHeight,texts};
                })};
            }""")
            assert metrics['bodyWidth']<=metrics['width']+1,metrics
            for score in metrics['scores']:
                assert score['svgCount'] and score['glyphMin']>=-3 and score['glyphMax']<=score['width']+3,score
                assert score['glyphBottom']<=score['height']+3,score
                if not metrics['bassTabs']:
                    assert all(t['height']>=10 for t in score['texts']),score
            if metrics['bassTabs']:
                # TAB fractions intentionally use smaller type; retain the existing
                # staff/TAB geometry contract rather than applying chord-label sizing.
                assert all(t['ok'] for t in metrics['bassTabs']),metrics
                for t in metrics['bassTabs']:
                    assert all(x['tabTop']>=x['nativeBottom']+4 for x in t['layouts'])
                if score['width']>score['client']+2:
                    assert score['overflow']=='auto',score
            regions=frame.locator('.ami-score-scroll')
            for i in range(regions.count()):
                region=regions.nth(i)
                region.evaluate('(e)=>e.scrollLeft=0')
                if region.evaluate('(e)=>e.scrollWidth>e.clientWidth+2'):
                    # A real keyboard action must move the local score, not the page.
                    region.focus();region.press('ArrowRight');page.wait_for_timeout(200)
                    assert region.evaluate('(e)=>e.scrollLeft')>0
                    region.evaluate('(e)=>e.scrollLeft=e.scrollWidth')
                    assert region.evaluate('(e)=>Math.abs(e.scrollWidth-e.clientWidth-e.scrollLeft)<2')
            frame.evaluate('window.scrollTo(0,document.body.scrollHeight)')
            iframe.screenshot(path=str(out/(tag+'-end-score.png')))
            frame.evaluate("window.scrollTo(0,0);document.querySelectorAll('.ami-score-scroll').forEach(e=>e.scrollLeft=0)")
            frames.append(metrics)
        geometry=page.evaluate("""() => ({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,x:scrollX})""")
        assert geometry['scrollWidth']<=geometry['width']+1,geometry
        geometry['frames']=frames
        (out/(tag+'-geometry.json')).write_text(json.dumps(geometry,indent=2),encoding='utf-8')
        page.screenshot(path=str(out/(tag+'-viewport.png')))
        panel.locator('iframe').first.screenshot(path=str(out/(tag+'-score.png')))
    import walk_guitar_shape_key as catalog_ui,walk_creative_backing_matrix as existing_ui
    catalog_ui.OUT=out/'catalog';existing_ui.OUT=out/'catalog';catalog_ui.OUT.mkdir(exist_ok=True)
    assert catalog_ui.pick_song(page,[],'Satin Doll','Jazz')
    page.locator('.st-key-studio_quick_nav_btn_practice button:visible').first.click()
    page.get_by_test_id('stMainBlockContainer').get_by_role('textbox',name='Question',exact=True).wait_for(timeout=90000)
    select(page,'Instrument','Saxophone')
    request(page,'Give me an advanced soprano sax jazz anticipation exercise in sixteenth notes over Satin Doll.','Jazz untied anticipations','layout-soprano')
    audit('desktop-soprano')
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(1800);audit('mobile-soprano')

    page.set_viewport_size({'width':1440,'height':1000})
    request(page,'Give me a ten-minute alto sax jazz improvisation warmup over Satin Doll.','10-minute Advanced','layout-long-plan')
    audit('desktop-long-plan')
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(1500);audit('mobile-long-plan')
    for instrument,q,cue in [
        ('Flute','Give me a difficult flute fingering exercise.','Flute octave and finger coordination'),
        ('Clarinet','Give me a clarinet octave exercise from F to F.','Octave jumps'),
        ('Trumpet','Give me a beginner trumpet lip-slur exercise.','lip-slur partial'),
        ('Bass Guitar','Give me an E minor bass scale.','Bass guitar scale')]:
        page.set_viewport_size({'width':1440,'height':1000})
        if instrument!='Bass Guitar':select(page,'Instrument',instrument)
        request(page,q,cue,'layout-'+instrument.lower().replace(' ','-'))
        audit('desktop-'+instrument.lower().replace(' ','-'))
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(1500)
        audit('mobile-'+instrument.lower().replace(' ','-'))
