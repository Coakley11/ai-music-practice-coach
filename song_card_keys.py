"""Key presentation for the Songs and Backing cards (v12 key-caption rule).

Both keys on these cards are concert pitch, so each value carries a "Concert pitch"
caption. A distance line appears only when the Practice Key differs from the Original
Key in the same mode: the shortest distance in semitones (1-5 higher or lower; 6 is
"a tritone away", with no direction). It is hidden when the keys match (enharmonic
spellings count as the same key), when the modes differ, and it never describes the
written pitch of a transposing instrument. Pure functions, no Streamlit.
"""
from __future__ import annotations

import re

_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_KEY_RE = re.compile(r"^\s*([A-Ga-g])\s*([#b♯♭]*)\s*(.*)$")


def _parse(key: str) -> tuple[int, str] | None:
    """(pitch class, 'major'|'minor') for 'Db', 'C#m', 'Eb minor', 'D♭ major'; None if unreadable."""
    m = _KEY_RE.match(str(key or ""))
    if not m:
        return None
    pc = _PC[m.group(1).upper()]
    for ch in m.group(2):
        pc += 1 if ch in "#♯" else -1
    rest = m.group(3).strip().lower()
    minor = rest.startswith("min") or (rest.startswith("m") and not rest.startswith("maj"))
    return pc % 12, ("minor" if minor else "major")


def pretty_key_name(key: str) -> str:
    """'Db' -> 'D♭ major', 'C#m' -> 'C♯ minor', 'Eb minor' -> 'E♭ minor'; unreadable text unchanged."""
    m = _KEY_RE.match(str(key or ""))
    if not m or _parse(key) is None:
        return str(key or "")
    acc = m.group(2).replace("#", "♯").replace("b", "♭")
    mode = _parse(key)[1]
    return f"{m.group(1).upper()}{acc} {mode}"


def same_key(a: str, b: str) -> bool:
    pa, pb = _parse(a), _parse(b)
    return pa is not None and pa == pb


def key_relation_caption(original: str, practice: str) -> str:
    """'2 semitones higher' / '1 semitone lower' / 'a tritone away', or '' (same key, mode change, unreadable)."""
    po, pp = _parse(original), _parse(practice)
    if po is None or pp is None or po[1] != pp[1] or po[0] == pp[0]:
        return ""
    d = (pp[0] - po[0]) % 12
    if d == 6:
        return "a tritone away"
    n, way = (d, "higher") if d < 6 else (12 - d, "lower")
    return f"{n} semitone{'s' if n != 1 else ''} {way}"


def key_token_from_name(name: str) -> str:
    """Inverse of pretty_key_name: 'D♭ major' -> 'Db', 'C♯ minor' -> 'C#m'; a bare token is returned as is."""
    m = _KEY_RE.match(str(name or ""))
    parsed = _parse(name)
    if not m or parsed is None:
        return str(name or "")
    acc = m.group(2).replace("♯", "#").replace("♭", "b")
    return f"{m.group(1).upper()}{acc}{'m' if parsed[1] == 'minor' else ''}"


# --- Search aliases for the Practice Key dropdowns ---------------------------------
# Streamlit 1.61's selectbox filters only on the visible option text, so "Eb" never
# matched "E♭ major". A script, installed once per page, rewrites what the user types
# in the two key dropdowns, and the dropdowns filter by prefix, so what the search says
# is what it finds:
#   "Eb" -> "E♭", "F#" -> "F♯"     the note
#   "F#m" -> "F♯ mi"               minor: finds F♯ minor, and nothing in a major-only list
#   "FM" -> "F ma"                 major: finds F major, and nothing in a minor-only list
# A mode the user states is never swapped for another. Only the search text changes: the
# options, stored key values, saved keys and callbacks are untouched.
KEY_SEARCH_ALIAS_SLOT_KEY = "key_search_alias_slot"
KEY_SEARCH_FILTER_MODE = "prefix"
KEY_SEARCH_INPUT_SELECTOR = (
    '.st-key-picker_active_song_practice_key_row input[role="combobox"], '
    '.st-key-backing_card_key_row input[role="combobox"]'
)
_NOTE = "([A-Ga-g][♭♯]?)"
# (pattern, replacement), applied in order to the whole search text; the one source for
# both the browser script and the tests. Later rules keep typing natural after the first
# rewrite: "F♯m" + "a" is "F♯ ma" ("F#maj"), "F♯m" + "i" stays "F♯ mi" ("F#min").
KEY_SEARCH_RULES: tuple[tuple[str, str], ...] = (
    (r"^\s*([A-Ga-g])b", "$1♭"),
    (r"^\s*([A-Ga-g])#", "$1♯"),
    (rf"^{_NOTE}(m[ai].*)$", "$1 $2"),
    (rf"^{_NOTE}M$", "$1 ma"),
    (rf"^{_NOTE}m$", "$1 mi"),
    (rf"^{_NOTE} mi[aA](.*)$", "$1 ma$2"),
    (rf"^{_NOTE} mi[iI](.*)$", "$1 mi$2"),
    (rf"^{_NOTE} ma[aA](.*)$", "$1 ma$2"),
)


def key_search_text(typed: str) -> str:
    """What the search box holds after ``typed`` (the browser script's rules, in Python)."""
    text = str(typed or "")
    for pattern, replacement in KEY_SEARCH_RULES:
        # $1 / $2 as in the browser's String.replace.
        text = re.sub(
            pattern,
            lambda m, r=replacement: re.sub(r"\$(\d)", lambda g: m.group(int(g.group(1))) or "", r),
            text,
        )
    return text


KEY_SEARCH_ALIAS_JS = """
<script>
(function () {
  var W = window.parent, D;
  try { D = W.document; } catch (e) { return; }
  W.__keySearchRules = %s;
  if (W.__keySearchAliasInstalled) return;
  W.__keySearchAliasInstalled = true;
  var SEL = %s;
  var setter = Object.getOwnPropertyDescriptor(W.HTMLInputElement.prototype, 'value').set;
  D.addEventListener('input', function (e) {
    var el = e.target;
    if (!el || e.__keySearchAlias || !el.matches || !el.matches(SEL)) return;
    var v = String(el.value || ''), nv = v;
    (W.__keySearchRules || []).forEach(function (r) { nv = nv.replace(new RegExp(r[0]), r[1]); });
    if (nv === v) return;
    // Replace the typed text before the combo box sees it, then let it filter.
    e.stopImmediatePropagation();
    var pos = el.selectionStart, atEnd = pos === v.length;
    setter.call(el, nv);
    try { el.setSelectionRange(atEnd ? nv.length : pos, atEnd ? nv.length : pos); } catch (e2) {}
    var ev = new W.Event('input', { bubbles: true });
    ev.__keySearchAlias = true;
    el.dispatchEvent(ev);
  }, true);
})();
</script>
"""


def key_search_alias_html() -> str:
    import json

    return KEY_SEARCH_ALIAS_JS % (
        json.dumps([list(r) for r in KEY_SEARCH_RULES], ensure_ascii=False),
        json.dumps(KEY_SEARCH_INPUT_SELECTOR),
    )


def render_key_search_alias(st) -> None:
    """Install the search-alias script (idempotent in the page). Call it on every run of
    a render path that draws a key dropdown, so its element slot is always present."""
    slot = st.container(key=KEY_SEARCH_ALIAS_SLOT_KEY)
    try:
        import streamlit.components.v1 as components
    except ImportError:  # pragma: no cover
        return
    with slot:
        components.html(key_search_alias_html(), height=0)
