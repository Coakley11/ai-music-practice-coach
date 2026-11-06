import json,time,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(encoding='utf8');out=Path('evidence/custom-key-fix');rows=[]
def state():return json.loads((out/'state.json').read_text())
protected=['song','active_catalog_pick_key','active_music_source','instrument','display_key','concert_key','concert_practice_key']
def save(): (out/'browser-results.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,args=['--renderer-process-limit=1']);page=b.new_page(viewport={'width':1440,'height':1000})
 def settle(after):
  end=time.time()+120
  while time.time()<end:
   page.wait_for_timeout(200)
   if (out/'state.json').exists() and state()['observed_at']>after and not page.get_by_role('button',name='Stop',exact=True).is_visible():page.wait_for_timeout(400);return
  raise TimeoutError('app completion timeout')
 def nav(key,homecard=False):
  before=state();t=time.perf_counter();now=time.time()
  selector='.st-key-home_nav_'+key+' button' if homecard else '.st-key-studio_quick_nav_btn_'+key+' button:visible'
  page.locator(selector).first.click()
  if key=='home':page.locator('.home-art').first.wait_for(timeout=120000)
  else:page.locator('.home-art').first.wait_for(state='hidden',timeout=120000)
  settle(now);after=state()
  row={'action':key,'home_card':homecard,'seconds':round(time.perf_counter()-t,3),'before':before,'after':after,'changes':{k:{'before':before[k],'after':after[k]} for k in protected if before[k]!=after[k]},'exceptions':page.locator('[data-testid=stException]').count()};rows.append(row);save();print(key,row['seconds'],row['changes'],flush=True)
  assert not row['changes'] and not row['exceptions']
 try:
  t=time.perf_counter();now=time.time();page.goto('http://127.0.0.1:8538/?suite_workspace=guest');page.locator('.home-art').first.wait_for(timeout=180000);settle(now);rows.append({'action':'cold_load','seconds':round(time.perf_counter()-t,3),'state':state()});save()
  page.get_by_role('combobox',name='Instrument',exact=True).click();now=time.time();page.get_by_role('option',name='Guitar',exact=True).click();settle(now)
  nav('more_custom',True)
  assert state()['display_key']=='G' and state()['custom_preview_key']=='C'
  for width,name in [(1440,'desktop'),(390,'mobile')]:
   page.set_viewport_size({'width':width,'height':1000});page.wait_for_timeout(300);page.screenshot(path=str(out/('custom-'+name+'.png')));(out/('custom-'+name+'.txt')).write_text(page.inner_text('body'),encoding='utf8')
  page.set_viewport_size({'width':1440,'height':1000})
  nav('practice');nav('backing');nav('picker');nav('custom');nav('practice');nav('custom');nav('practice')
  # Custom preview edits remain independent of the active Catalog key.
  nav('custom');before=state();c=page.get_by_role('combobox',name='Custom workspace Practice / Concert Key',exact=True);c.click();now=time.time();page.get_by_role('option',name='Eb',exact=True).click();settle(now);after=state();rows.append({'action':'edit_custom_preview','before':before,'after':after,'changes':{k:{'before':before[k],'after':after[k]} for k in protected if before[k]!=after[k]}});save();assert after['display_key']=='G';assert after['custom_preview_key']=='Eb';nav('practice');nav('backing')
 except Exception as e:
  rows.append({'action':'error','error':str(e)});save();page.screenshot(path=str(out/'browser-error.png'));(out/'browser-error.txt').write_text(page.inner_text('body'),encoding='utf8');raise
 finally:b.close()
