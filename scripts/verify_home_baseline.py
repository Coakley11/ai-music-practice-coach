import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import songs.state
import pytest
source = subprocess.check_output(['git','show','origin/dev:songs/state.py']).decode('utf8')
exec(compile(source, songs.state.__file__, 'exec'), songs.state.__dict__)
raise SystemExit(pytest.main(['tests/test_pick_key.py','tests/test_active_pick_key_reconciliation.py','tests/test_cpl_set_active_song.py','tests/test_v19_restore_guard.py','tests/test_source_authority_coherence.py','-q','--tb=no']))
