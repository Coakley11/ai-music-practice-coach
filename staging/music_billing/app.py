"""Community Cloud entry point: no full Music/Suite app imports."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
from staging.music_billing.frontend import render

render(st)
