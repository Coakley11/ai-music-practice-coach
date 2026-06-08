"""Minimal app to verify top nav sizing — run: streamlit run scripts/nav_visual_test.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import streamlit as st

from app_ui import inject_app_theme, render_page_quick_nav

st.set_page_config(page_title="Nav test", layout="wide")
inject_app_theme()
st.title("Top navigation sizing test")
render_page_quick_nav(
    st.session_state,
    current_page="practice",
    rerun_fn=st.rerun,
)
st.caption("Icon + script labels with Open buttons; active page should be red/purple.")
