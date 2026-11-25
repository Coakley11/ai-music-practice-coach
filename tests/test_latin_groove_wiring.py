"""Slice 3 wiring: with MUSIC_LATIN_GROOVES a Creative "Latin" jam plays Latin jazz, a "Samba" jam plays Samba, and both
are Backing Feel choices; Bossa nova stays Bossa nova. With the switch off nothing changes (Latin and Samba still play
the Bossa nova groove, no new choices appear). The lists are fixed at import, so the switched-on case runs in a child
interpreter."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROBE = """
import json
from songs.playback_defaults import GROOVE_STYLE_CHOICES as G, normalize_groove_label as n
from improvisation_intelligence import STYLE_JAM_STYLES as S, generate_style_progression as g
out = {"choices": list(G), "styles": list(S),
       "map": {x: n(x) for x in ("Latin", "Samba", "Bossa Nova", "Bossa nova", "Latin jazz", "Jazz Swing")}}
if "Samba" in S:
    out["samba"] = g(style="Samba", key_center="D")
    out["samba_minor"] = g(style="Samba", key_center="Em")
print("JSON" + json.dumps(out))
"""


def _probe(switch: str | None) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "MUSIC_LATIN_GROOVES"}
    if switch is not None:
        env["MUSIC_LATIN_GROOVES"] = switch
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    res = subprocess.run([sys.executable, "-c", PROBE], cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=300)
    line = next(ln for ln in res.stdout.splitlines() if ln.startswith("JSON"))
    return json.loads(line[4:])


def test_switch_off_changes_nothing():
    off = _probe(None)
    assert "Samba" not in off["choices"] and "Latin jazz" not in off["choices"]
    assert "Samba" not in off["styles"]
    assert off["map"]["Latin"] == off["map"]["Samba"] == "Bossa nova"


def test_switch_on_routes_latin_and_samba_and_keeps_bossa():
    on = _probe("1")
    assert on["choices"][-2:] == ["Samba", "Latin jazz"]
    assert on["styles"][-1] == "Samba"
    assert on["map"]["Latin"] == "Latin jazz" and on["map"]["Samba"] == "Samba"
    assert on["map"]["Bossa Nova"] == on["map"]["Bossa nova"] == "Bossa nova"
    assert on["map"]["Jazz Swing"] == "Jazz swing"
    # A Samba jam's sections are its own ("<part> (Samba)"), with samba harmony (I - VI7 - ii - V in D).
    assert list(on["samba"]) == ["A (Samba)", "B (Samba)", "A' (Samba)"]
    assert on["samba"]["A (Samba)"][:4] == ["D6", "B7", "Em7", "A7"]  # the generator may extend the first section
    assert on["samba_minor"]["A (Samba)"][0].startswith("Em")
