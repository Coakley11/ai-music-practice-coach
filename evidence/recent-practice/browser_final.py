import json,time,sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(encoding='utf8');out=Path('evidence/recent-practice');style=Path('evidence/purple-sidebar');rows=[]
def state():return json.loads((out/'state.json').read_text())
def save():(out/'browser-final-results.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
protected=['song','active_catalog_pick_key','active_music_source','instrument','display_key','concert_practice_key','focus','keys']
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,args=['--renderer-process-limit=1']);page=b.new_page(viewport={'width':1440,'height':1000})
 def settle(after):
  end=time.time()+150
  while time.time()<end:
   page.wait_for_timeout(250)
   if (out/'state.json').exists() and state()['observed_at']>after and not page.get_by_role('button',name='Stop',exact=True).is_visible():page.wait_for_timeout(500);return
  raise TimeoutError('app completion timeout')
 def snap(name):page.screenshot(path=str(style/(name+'.png')))
 def action(name,fn,unchanged=False):
  before=state();now=time.time();start=time.perf_counter();fn();settle(now);after=state();row={'action':name,'seconds':round(time.perf_counter()-start,3),'before':before,'after':after,'exceptions':page.locator('[data-testid=stException]').count()};rows.append(row);save();print(name,row['seconds'],after['song'],after['display_key'],flush=True);assert row['exceptions']==0
  if unchanged:assert all(before[k]==after[k] for k in protected),name
 def nav(key):action(key,lambda:page.locator('.st-key-studio_quick_nav_btn_'+key+' button:visible').first.click(),True)
 def css():
  return page.locator('[data-testid=stSidebar]').evaluate('''e=>({background:getComputedStyle(e).backgroundColor,buttons:[...e.querySelectorAll('button[data-testid="stBaseButton-secondary"]')].filter(b=>b.offsetWidth).map(b=>({text:b.innerText,disabled:b.disabled,background:getComputedStyle(b).backgroundColor,color:getComputedStyle(b.querySelector('p')||b).color,opacity:getComputedStyle(b).opacity})),main:getComputedStyle(document.querySelector('[data-testid="stMain"]')).backgroundColor,header:getComputedStyle(document.querySelector('.ui-brand-header')).backgroundImage})''')
 try:
  fixture=json.loads((out/'all-the-things-fixture.json').read_text());fixture['workspace_id']='test_user'
  now=datetime.now(ZoneInfo('America/New_York'));fixture.update(date=now.date().isoformat(),created_at=now.isoformat())
  fixture_path=out/'browser-runtime/workspaces/test_user/practice_history.json';fixture_path.parent.mkdir(parents=True,exist_ok=True);fixture_path.write_text(json.dumps([fixture]),encoding='utf8')
  (fixture_path.parent/'music_user_state.json').unlink(missing_ok=True)  # own disposable fixture workspace only
  r={'key':fixture['original_key']}
  action('fresh-all-the-things-fixture',lambda:page.goto('http://127.0.0.1:8541/?suite_workspace=test_user'))
  assert state()['song']['title']=='Say' and state()['display_key']=='G'
  page.evaluate('document.querySelector("[data-testid=stMain]").scrollTop=0');snap('desktop-purple-sidebar')
  rows.append({'action':'computed-styles','styles':css()});save();assert css()['background']=='rgb(49, 46, 129)'
  page.locator('.home-continue').scroll_into_view_if_needed();snap('desktop-before-all-the-things-resume')
  action('resume-all-the-things',lambda:page.locator('.st-key-home_resume_btn button').click())
  s=state();assert s['song']['title']=='All the Things You Are' and s['instrument']=='Saxophone' and s['display_key']=='Eb' and s['keys']['written_key']=='F' and s['song']['key']==r['key']
  nav('picker');snap('desktop-songs-synchronized');nav('practice');nav('backing');nav('home');page.locator('.home-continue').scroll_into_view_if_needed();snap('desktop-recent-practice')
  page.set_viewport_size({'width':390,'height':900});page.wait_for_timeout(500)
  sidebar=page.locator('[data-testid=stSidebar]')
  if sidebar.bounding_box()['x']<0:page.locator('[data-testid=stExpandSidebarButton]').click();page.wait_for_timeout(400)
  page.locator('[data-testid=stSidebarContent]').evaluate('(e)=>e.scrollTop=0');snap('mobile-purple-expanded')
  page.locator('[data-testid=stSidebarContent]').evaluate('(e)=>e.scrollTop=300');snap('mobile-purple-controls')
  key=sidebar.get_by_role('combobox',name='🗝️ Practice / Concert Key',exact=True);key.click();page.wait_for_timeout(300);snap('mobile-key-dropdown');page.keyboard.press('Escape')
  page.locator('[data-testid=stSidebarContent]').evaluate('(e)=>e.scrollTop=0')
  sidebar.get_by_text('Account & Workspace',exact=True).click();page.wait_for_timeout(300);snap('mobile-account-expanded')
  page.locator('[data-testid=stSidebarCollapseButton]').click();page.wait_for_timeout(500)
  page.locator('.home-continue').scroll_into_view_if_needed();snap('mobile-purple-collapsed')
  # Repeat the actual Resume interaction in the mobile layout.
  action('mobile-repeat-resume',lambda:page.get_by_role('button',name='Resume Practice',exact=True).click(),True)
  rows.append({'action':'final','state':state()});save()
 except Exception as e:
  rows.append({'error':str(e)});save();page.screenshot(path=str(out/'browser-final-error.png'));(out/'browser-final-error.txt').write_text(page.inner_text('body'),encoding='utf8');raise
 finally:b.close()
