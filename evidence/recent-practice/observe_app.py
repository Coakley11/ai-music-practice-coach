import runpy,json,time,traceback
from pathlib import Path
import streamlit as st
from streamlit.runtime.state.session_state import SessionState
root=Path(__file__).resolve().parents[2];out=root/'evidence'/'recent-practice'
@st.cache_resource(show_spinner=False)
def app_code():
 t=time.perf_counter();code=compile((root/'streamlit_music_practice_app.py').read_bytes(),str(root/'streamlit_music_practice_app.py'),'exec')
 (out/'compile-time.json').write_text(json.dumps({'seconds':time.perf_counter()-t}));return code
if not getattr(SessionState,'_custom_key_acceptance_hook',False):
 original=SessionState.__setitem__
 def observe(self,key,value):
  if key in ('selected_song','display_key','concert_key','concert_practice_key','active_music_source','active_catalog_pick_key'):
   try:before=self[key]
   except KeyError:before=None
   if before!=value:
    row={'time':time.time(),'key':key,'before':before,'after':value,'stack':[f'{Path(f.filename).name}:{f.lineno}:{f.name}' for f in traceback.extract_stack(limit=7)[:-1]]}
    with (out/'browser-key-writes.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(row,default=str)+'\n')
  return original(self,key,value)
 SessionState.__setitem__=observe;SessionState._custom_key_acceptance_hook=True
code=app_code();start=time.perf_counter();cpu=time.process_time();outcome='completed'
try:
 runpy._run_module_code(code,mod_name='__main__',script_name=str(root/'streamlit_music_practice_app.py'))
except BaseException as e:
 outcome=type(e).__name__;raise
finally:
 timing={'page':st.session_state.get('studio_page'),'run':st.session_state.get('_script_run_seq'),'outcome':outcome,'wall_seconds':round(time.perf_counter()-start,3),'cpu_seconds':round(time.process_time()-cpu,3),'time':time.time()}
 with (out/'run-timings.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(timing)+'\n')
 if outcome=='completed':
  keys=['studio_page','active_catalog_pick_key','active_music_source','instrument','display_key','concert_key','concert_practice_key','_pending_display_key','cpl_workspace_practice_key','_music_nav_cloud_read_timings','_script_run_seq']
  data={k:st.session_state.get(k) for k in keys};song=st.session_state.get('selected_song') or {};data['song']={k:song.get(k) for k in ['title','key','pick_key']};data['observed_at']=time.time();data['focus']=st.session_state.get('focus');data['transposing_type']=st.session_state.get('selected_transposing_instrument');data['capo']=st.session_state.get('guitar_capo_fret')
  from instrument_transposition import resolve_practice_keys
  data['keys']=resolve_practice_keys(dict(st.session_state),str(st.session_state.get('display_key') or ''),str(st.session_state.get('instrument') or 'Piano'))
  from custom_progression_lab import cpl_workspace_practice_key,CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET
  data['custom_preview_key']=st.session_state.get(CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET)
  (out/'state.json').write_text(json.dumps(data,default=str,indent=2),encoding='utf8')
