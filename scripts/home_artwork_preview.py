"""Isolated visual comparison of the baseline and current Home renderer."""
import subprocess
import sys
import types
from pathlib import Path
import streamlit as st
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
st.set_page_config(page_title='Home artwork review',layout='wide')
if st.query_params.get('revision')=='before':
    module=types.ModuleType('baseline_home')
    module.__file__=str(ROOT/'home_page.py')
    source=subprocess.check_output(['git','show','ea12085d:home_page.py'],cwd=ROOT).decode('utf8')
    exec(compile(source,module.__file__,'exec'),module.__dict__)
else:
    import home_page as module
module.verified_recent_session=lambda _: None
with st.container(key='home_page'):
    module.render_home_page(st,st.session_state,rerun_fn=st.rerun)
