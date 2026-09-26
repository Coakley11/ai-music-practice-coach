@echo off
cd /d "C:\Users\danie\Documents\GitHub\ai-music-practice-coach-keycycle-dev-integ"
python -m streamlit run streamlit_music_practice_app.py --server.port 8510 --server.headless true --server.address 127.0.0.1 --browser.gatherUsageStats false --server.fileWatcherType none >> "scripts\evidence-key-cycle\streamlit_8510_detached.out.log" 2>> "scripts\evidence-key-cycle\streamlit_8510_detached.err.log"
