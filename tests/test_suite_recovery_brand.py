"""Recovery forms must show the packaged official artwork before form headings."""
import ast
from pathlib import Path
from typing import Any
import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'suite_auth.py'

@pytest.mark.parametrize('name', [
    '_render_password_recovery_panel', '_render_recovery_verify_failed',
    '_render_recovery_bare_site_landing', '_render_recovery_landing_failed',
])
def test_recovery_screen_renders_official_artwork_before_heading(name):
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    # Exercise the real presentation prefix without authentication or side effects.
    class HeadingReached(Exception):
        pass
    class Target:
        markup = []
        def markdown(self, value, **kwargs):
            self.markup.append(value)
        def title(self, value):
            assert self.markup and 'data:image/png;base64,' in self.markup[0]
            assert 'alt="Daniel AI Suite"' in self.markup[0]
            raise HeadingReached
    namespace = {'Any': Any}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), 'exec'), namespace)
    with pytest.raises(HeadingReached):
        namespace[name](Target())
