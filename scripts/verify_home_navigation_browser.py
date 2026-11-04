import json
from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path('evidence/home-handoff')
with sync_playwright() as p:
 b=p.chromium.launch(headless=True); page=b.new_page(viewport={'width':1440,'height':1000})
 def idle():
  page.wait_for_timeout(900)
  page.get_by_role('button',name='Stop',exact=True).wait_for(state='hidden',timeout=90000)
 def home():
  page.wait_for_timeout(1500); page.locator('.st-key-studio_quick_nav_btn_home button:visible').first.click(); page.get_by_text('Catalog browsing',exact=False).wait_for(state='hidden',timeout=60000); idle()
  page.locator('.home-art').first.wait_for(timeout=120000)
 page.goto('http://127.0.0.1:8527/?suite_workspace=guest'); page.locator('.st-key-studio_quick_nav_btn_home button:visible').first.wait_for(timeout=120000); idle()
 if not page.locator('.home-art').count(): home()
 results=[]
 for key,expected in [('discover_pop','Pop'),('discover_jazz','Jazz'),('discover_all','all')]:
  print('Checking',key,flush=True)
  page.locator('.st-key-home_nav_'+key+' button').click(); page.get_by_text('Catalog browsing',exact=False).wait_for(timeout=60000); idle()
  body=page.inner_text('body'); (out/(key+'.txt')).write_text(body,encoding='utf8')
  assert 'Catalog browsing' in body
  assert 'Say' in page.locator('[data-testid="stSidebar"]').inner_text()
  assert not page.locator('[data-testid="stException"]').count()
  page.screenshot(path=str(out/(key+'.png')))
  results.append({'route':key,'catalog_view':True,'active_song':'Say','exception':False})
  home()
 for key,needle in [('more_missions','Missions'),('more_sbi','Song-Aware Coaching'),('more_analysis','Upload'),('more_keycycle','Advanced playback settings')]:
  print('Checking',key,flush=True)
  page.locator('.st-key-home_nav_'+key+' button').click(); page.locator('.home-art').first.wait_for(state='hidden',timeout=60000); idle()
  body=page.inner_text('body'); (out/(key+'.txt')).write_text(body,encoding='utf8')
  assert needle in body, key
  if key=='more_sbi': assert 'Build My Coaching Plan' in body
  if key=='more_analysis': assert 'Run AI coach analysis' in body
  assert not page.locator('[data-testid="stException"]').count(),key
  if key=='more_keycycle':
   expander=page.locator('[data-testid="stExpander"]').filter(has_text='Advanced playback settings').first
   assert expander.locator('details').get_attribute('open') is not None
   assert page.locator('audio').evaluate_all('(els)=>els.every(a=>a.paused)')
  results.append({'route':key,'destination_text':needle,'exception':False})
  (out/'navigation-results.json').write_text(json.dumps(results,indent=2),encoding='utf8')
  if key!='more_keycycle': home()
 (out/'navigation-results.json').write_text(json.dumps(results,indent=2),encoding='utf8')
 print(json.dumps(results)); b.close()
