"""Attach stored bass TAB to the existing ABCJS notation component."""
import json
from pathlib import Path
from functools import lru_cache

@lru_cache(maxsize=1)
def script():
    return Path(__file__).with_name('bass_tab.js').read_text(encoding='utf-8-sig')

def render_call(div_id,abc,tab):
    def safe(value):return json.dumps(value,ensure_ascii=True).replace('<','\\u003c')
    return script()+'\namiRenderBassTab('+','.join(map(safe,[div_id,abc,tab]))+');'
