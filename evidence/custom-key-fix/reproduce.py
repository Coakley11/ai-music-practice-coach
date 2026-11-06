import sys,json,traceback,copy
from pathlib import Path
from types import SimpleNamespace
root=Path(sys.argv[1]).resolve();sys.path.insert(0,str(root))
from custom_progression_lab import prepare_custom_workspace_sidebar_display_key,CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET
from app_ui import navigate_studio_page
class Traced(dict):
 def __setitem__(self,k,v):
  if k in ('display_key','concert_key','_pending_display_key') and self.get(k)!=v:
   writes.append({'key':k,'before':self.get(k),'after':v,'stack':[f'{Path(f.filename).name}:{f.lineno}:{f.name}' for f in traceback.extract_stack(limit=6)[:-1]]})
  super().__setitem__(k,v)
rows=[]
for page in ['home','practice','picker']:
 writes=[];pick='Pop\x1fSay — John Mayer'
 s=Traced(studio_page=page,selected_song={'title':'Say','key':'G','pick_key':pick},active_catalog_pick_key=pick,active_music_source='catalog_song',instrument='Guitar',display_key='G',concert_key='G',concert_practice_key='G',practice_key_by_source={pick:'G'})
 before=copy.deepcopy(dict(s))
 if page=='home':
  from home_destinations import apply_home_navigation,destination_by_key
  apply_home_navigation(s,destination_by_key('more_custom'))
 else:navigate_studio_page(s,'custom')
 prepare_custom_workspace_sidebar_display_key(SimpleNamespace(session_state=s),s)
 fields=['active_catalog_pick_key','active_music_source','instrument','display_key','concert_key','concert_practice_key']
 rows.append({'entry':page,'before':{k:before[k] for k in fields},'after':{k:s[k] for k in fields},'preview_key':s[CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET],'writes':writes})
print(json.dumps(rows,indent=2,ensure_ascii=True))

