import math,json
from pathlib import Path
from playwright.sync_api import sync_playwright
OUT=Path('evidence/home-distinct-artwork')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--renderer-process-limit=1'])
    page=browser.new_page(viewport={'width':1140,'height':7000})
    page.goto('http://127.0.0.1:8531/?revision=after',wait_until='domcontentloaded')
    page.locator('.st-key-home_card_more_log').wait_for(timeout=120000)
    page.get_by_role('button',name='Stop',exact=True).wait_for(state='hidden',timeout=120000)
    results=[]
    for name,width in [('desktop',1140),('mobile',390)]:
        page.set_viewport_size({'width':width,'height':8000}); page.wait_for_timeout(500)
        frame=page.locator('.st-key-home_page'); box=frame.bounding_box()
        page.set_viewport_size({'width':width,'height':math.ceil(box['height']+300)}); page.wait_for_timeout(300)
        frame.screenshot(path=str(OUT/(name+'-full.png')))
        def capture_section(first,last,label):
            a=page.locator(first).bounding_box(); b=page.locator(last).bounding_box()
            left=min(a['x'],b['x']); top=min(a['y'],b['y'])
            right=max(a['x']+a['width'],b['x']+b['width']); bottom=max(a['y']+a['height'],b['y']+b['height'])
            page.screenshot(path=str(OUT/(name+'-'+label+'.png')),clip={'x':left,'y':top,'width':right-left,'height':bottom-top})
        capture_section('.home-continue','.st-key-home_card_journey_composer','recent-workflows')
        capture_section('.st-key-home_card_discover_pop','.st-key-home_card_discover_all','pop-jazz')
        capture_section('.st-key-home_card_more_missions','.st-key-home_card_more_log','tools')
        buttons=page.locator('[class*=st-key-home_nav_] button').evaluate_all('(els)=>els.map(e=>({width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height}))')
        assert len(buttons)==13 and all(b['width']>=44 and b['height']>=44 for b in buttons)
        boxes=page.locator('[class*=st-key-home_card_]').evaluate_all('(els)=>els.map(e=>({left:e.getBoundingClientRect().left,right:e.getBoundingClientRect().right}))')
        assert all(b['left']>=0 and b['right']<=width+1 for b in boxes)
        assert page.locator('.home-art').count()==13
        assert not page.locator('[data-testid=stException]').count()
        results.append({'viewport_width':width,'art_count':13,'touch_targets_at_least_44px':True,'cards_inside_viewport':True})
    # Browser rendering must preserve the same genre identities as the existing catalog.
    assert page.locator('.home-art-discover_pop svg').text_content().find('POP')>=0
    assert 'JAZZ' in page.locator('.home-art-discover_jazz svg').text_content()
    (OUT/'browser-results.json').write_text(json.dumps(results,indent=2),encoding='utf8')
    browser.close()
print(json.dumps(results))
