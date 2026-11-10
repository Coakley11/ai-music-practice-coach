from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import ast
from music_sidebar_policy import apply_page_defaults, home_sidebar_css, SidebarTarget, PAGES_COLLAPSED
from music_coaching_hub import CAPABILITIES, FUTURE_DIRECTIONS, render_coaching_hub


def test_page_defaults_follow_transitions_without_resetting_musical_state():
    music = {'instrument':'Saxophone','selected_transposing_instrument':'Tenor Saxophone',
             'display_key':'Ab','cpl_saved_progressions':{'Trial Song':{'key':'Eb'}},
             'composer_saved_compositions':{'piece':{'key':'D'}},'mt_tracks':{'tenor':b'audio'}}
    state=deepcopy(music)
    for page in ('home','practice','home','backing','picker','custom'):
        assert apply_page_defaults(state,page) == (page!='home')
        state[PAGES_COLLAPSED]=False
        assert not apply_page_defaults(state,page)  # a normal rerun respects the user's choice
        assert {key:state[key] for key in music}==music
    assert 'stSidebar' not in home_sidebar_css('home')  # never force the entire sidebar open
    assert 'display:none' in home_sidebar_css('home')
    assert not home_sidebar_css('practice')


def test_scoped_control_renderer_retains_real_session_and_callbacks():
    state={'instrument':'Piano'}
    real=SimpleNamespace(session_state=state,sidebar=object(),rerun=lambda:None)
    target=object();proxy=SidebarTarget(real,target)
    assert proxy.session_state is state and proxy.sidebar is target
    assert proxy.rerun is real.rerun


def test_page_order_and_working_widgets_remain_unconditionally_mounted():
    root=Path(__file__).resolve().parents[1]
    ui=(root/'app_ui.py').read_text(encoding='utf-8')
    start=ui.index('STUDIO_PAGE_META:');end=ui.index('# Canonical page accent',start)
    assert ui[start:end].index('"analysis":') < ui[start:end].index('"multitrack":')
    source=(root/'streamlit_music_practice_app.py').read_text(encoding='utf-8')
    tree=ast.parse(source)
    calls=[node for node in tree.body if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call)
           and isinstance(node.value.func,ast.Attribute) and getattr(node.value.func.value,'id','')=='_working_sidebar'
           and node.value.func.attr=='selectbox']
    assert any(any(k.arg=='key' and isinstance(k.value,ast.Constant) and k.value.value=='instrument' for k in n.value.keywords) for n in calls)
    assert any(any(k.arg=='key' and isinstance(k.value,ast.Constant) and k.value.value=='level' for k in n.value.keywords) for n in calls)
    assert 'feature_label("level", "Level")' in source


def test_hub_navigation_uses_existing_contract_and_never_starts_ai_work():
    class St:
        def __init__(self):self.labels=[]
        def markdown(self,*a,**kw):pass
        def caption(self,*a,**kw):pass
        def button(self,label,**kw):self.labels.append(label);return label=='Backing Tracks and Key Cycling'
    st=St();state={'display_key':'Ab'};before=deepcopy(state);calls=[]
    render_coaching_hub(st,state,lambda s,page:calls.append(page),lambda:calls.append('rerun'))
    assert calls==['backing','rerun'] and state==before
    assert len(st.labels)==8
    assert {'log','analysis','creative','composer','backing','practice'}=={c[0] for c in CAPABILITIES}
    assert not any('Practice summaries' in s or 'Recording comparisons' in s for s in FUTURE_DIRECTIONS)


def test_sidebar_text_and_gold_contrast_on_brand_surfaces():
    def luminance(color):
        values=[int(color[i:i+2],16)/255 for i in (1,3,5)]
        values=[v/12.92 if v<=0.04045 else ((v+0.055)/1.055)**2.4 for v in values]
        return sum(v*w for v,w in zip(values,(0.2126,0.7152,0.0722)))
    for foreground in ('#facc15','#e0e7ff'):
        for background in ('#0f172a','#211e54'):
            light,dark=sorted((luminance(foreground),luminance(background)),reverse=True)
            assert (light+0.05)/(dark+0.05)>4.5
