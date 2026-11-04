from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path('evidence/home-handoff')
with sync_playwright() as p:
 b=p.chromium.launch(headless=True)
 page=b.new_page(viewport={'width':1440,'height':1000})
 for revision in ('before','after'):
  page.set_viewport_size({'width':1440,'height':1000})
  page.goto('http://127.0.0.1:8528/?revision='+revision)
  card=page.locator('.st-key-home_card_journey_practice')
  card.wait_for(timeout=90000)
  page.wait_for_timeout(1200)
  card.scroll_into_view_if_needed()
  page.screenshot(path=str(out/(revision+'-comparison-desktop.png')))
  page.set_viewport_size({'width':390,'height':844})
  card.scroll_into_view_if_needed(); page.wait_for_timeout(500)
  page.screenshot(path=str(out/(revision+'-comparison-mobile.png')))
 b.close()
print('Baseline/current Home component comparison captured')
