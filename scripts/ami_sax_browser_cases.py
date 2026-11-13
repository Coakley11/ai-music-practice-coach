"""Real native SVG pitch, duration and articulation acceptance for saxophones."""
from fractions import Fraction
from tests.test_ami_sax_technique import check
from tests.song_oracle import read_tune


def run(page,request,select,out,probe=False):
 def ask(q,cue,tag):
  r,staff=request(page,q,cue,'sax-'+tag);p=r['plan'];check(p)
  view=r['history'].get('view',{});rows=p['items'][view.get('index',0):view.get('index',0)+1] if view.get('mode')=='item' else p['items']
  for score,row in zip(staff,rows):
   actual=score['notes'];tune=[e for e in read_tune(row['abc']) if e[2] is not None]
   assert [n['duration'] for n in actual]==[float(e[1]/4) for e in tune], 'Rendered rhythmic values differ from independent ABC timing'
   if row.get('articulations'):
    for n,art in zip(actual,row['articulations']):
     dec=n.get('decoration') or []
     assert ('accent' in dec)==('accent' in art),(dec,art)
     assert ('staccato' in dec)==('staccato' in art),(dec,art)
   if row.get('slur_groups'):
    starts=[];ends=[]
    for i,n in enumerate(actual):
     for field,into in [('startSlur',starts),('endSlur',ends)]:
      values=[n.get(field)]+[v.get(field) for v in n['pitches']]
      if any(values):into.append(i)
    groups=row['slur_groups'];expected_start=[i for i,g in enumerate(groups) if g and (i==0 or groups[i-1]!=g)];expected_end=[i for i,g in enumerate(groups) if g and (i==len(groups)-1 or groups[i+1]!=g)]
    assert starts==expected_start and ends==expected_end,(starts,ends,expected_start,expected_end)
  return r
 select(page,'Instrument','Saxophone');select(page,'Level','Intermediate');select(page,'Focus','Articulation')
 a=ask('Give me an alto sax exercise in thirds.','Saxophone diatonic thirds','01-alto')
 b=ask('Slur every two notes.','Updated only','02-pairs');assert b['plan']['items'][0]['written_midi']==a['plan']['items'][0]['written_midi']
 c=ask('Accent the first note of every group.','Updated only','03-accent')
 if probe:
  import walk_guitar_shape_key as catalog_ui,walk_creative_backing_matrix as existing_ui
  catalog_ui.OUT=out/'catalog';existing_ui.OUT=out/'catalog';catalog_ui.OUT.mkdir(exist_ok=True)
  assert catalog_ui.pick_song(page,[],'All the Things You Are','Jazz')
  page.locator('.st-key-studio_quick_nav_btn_practice button:visible').first.click()
  page.get_by_test_id('stMainBlockContainer').get_by_role('textbox',name='Question',exact=True).wait_for(timeout=90000)
  chart=ask('Give me a tenor sax articulation exercise using guide tones over the A3 section.','one chart pass','probe-a3')
  assert chart['plan']['spec']['song_sel']['section']=='A3' and chart['plan']['player']['key']=='tenor'
  return
 d=ask('Keep the pitches but make the rhythm more difficult.','Updated only','04-rhythm');assert d['plan']['items'][0]['written_midi']==c['plan']['items'][0]['written_midi']
 slow=ask('Make it slower.','Updated only','05-slower')
 why=ask('Explain what technique this develops.','This stored technique','06-explain');assert why['plan']==slow['plan'] and why['history']==slow['history']
 undo=ask('Undo.','Restored the exact stored version','07-undo');assert undo['plan']==d['plan']
 redo=ask('Redo.','Restored the exact stored version','08-redo');assert redo['plan']==slow['plan']
 revised=ask('Change the thirds to fourths.','Saxophone diatonic fourths','09-fourths');assert revised['plan']['items'][0]['durations']==slow['plan']['items'][0]['durations']
 ask('Now make it descending.','descending','10-descending')
 octaves=ask('Add octave jumps.','octaves','11-octaves');assert octaves['plan']['items'][0]['durations']==slow['plan']['items'][0]['durations']
 ask('Move it into a comfortable register.','no new version','12-comfortable')
 base=ask('Give me a beginner alto sax exercise in thirds.','Alto Saxophone, Beginner','13-adapt-start')
 target=ask('Adapt this to tenor sax.','Tenor Saxophone','14-tenor-adapt');assert target['settings']==base['settings']
 ask('Give me a tonguing exercise for tenor sax.','repeated-note tonguing','15-tenor-tongue')
 ask('Use staccato.','Updated only','16-staccato')
 ask('Give me something to improve my legato.','articulation scale','17-legato')
 ask('Give me an advanced alto sax finger-buster with accents.','finger coordination','18-buster')
 ask('Give me ascending fourths for soprano sax.','Soprano Saxophone','19-soprano')
 ask('Give me a baritone sax exercise in sixths.','Baritone Saxophone','20-baritone')
 ask('Give me an alto sax register transitions exercise.','middle-register transitions','21-transition')
 ask('Give me an alto sax chromatic coordination exercise.','chromatic finger coordination','22-chromatic')
 warm=ask('Make me a ten-minute tenor sax articulation warmup.','tenor saxophone warmup','23-routine');assert not warm['plan']['spec'].get('single') and len(warm['plan']['items'])>1
 assert len({tuple(row['written_midi']) for row in warm['plan']['items']})==len(warm['plan']['items'])
 import walk_guitar_shape_key as catalog_ui,walk_creative_backing_matrix as existing_ui
 catalog_ui.OUT=out/'catalog';existing_ui.OUT=out/'catalog';catalog_ui.OUT.mkdir(exist_ok=True)
 assert catalog_ui.pick_song(page,[],'Blue Bossa','Jazz')
 page.locator('.st-key-studio_quick_nav_btn_practice button:visible').first.click()
 page.get_by_test_id('stMainBlockContainer').get_by_role('textbox',name='Question',exact=True).wait_for(timeout=90000)
 chart=ask('Give me an alto sax articulation exercise using the guide tones.','one chart pass','24-guide-tones');assert chart['plan']['spec']['song']['title']=='Blue Bossa'
