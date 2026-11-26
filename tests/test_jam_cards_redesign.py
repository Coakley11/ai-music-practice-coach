"""Entry & Jam cards (Style Jam, Jam Session Generator): presentation only, controls untouched.

The redesign wraps the two tools' controls in keyed cards with artwork and read-only "what was
generated" panels. These tests pin that every jam widget keeps its exact key, label, options,
callback, args and creation order; that the cards' CSS is scoped to their own containers; that the
artwork is self-contained; and that the generated panels are built only from each tool's own data.
"""

from __future__ import annotations

import ast
import pathlib
import re
import unittest
import xml.etree.ElementTree as ET

import jam_card_art as jam_art

ROOT = pathlib.Path(__file__).resolve().parents[1]
UI = ROOT / "improvisation_intelligence_ui.py"

# Every jam widget as it was on dev 3587e435 (before the redesign): (call, positional args, keywords).
JAM_WIDGETS_BEFORE: dict[str, tuple] = {
    "improv_style": ("selectbox", ("'Style'", "list(STYLE_JAM_STYLES)"), (("key", "'improv_style'"), ("on_change", "on_improv_style_jam_setting_change"), ("persist_state", "'session'"))),
    "improv_style_key": ("selectbox", ("'Concert Key'", "_style_key_opts"), (("format_func", "display_key_label"), ("key", "'improv_style_key'"), ("on_change", "on_improv_style_key_change"), ("persist_state", "'session'"))),
    "improv_difficulty": ("selectbox", ("'Difficulty'", "list(DIFFICULTY_LEVELS)"), (("format_func", "level_label"), ("key", "'improv_difficulty'"), ("on_change", "on_improv_style_jam_setting_change"), ("persist_state", "'session'"))),
    "improv_mood": ("selectbox", ("'Mood'", "list(MOOD_OPTIONS)"), (("key", "'improv_mood'"), ("on_change", "on_improv_style_jam_setting_change"), ("persist_state", "'session'"))),
    "improv_style_bpm": ("slider", ("'Tempo (BPM)'", "60", "200"), (("key", "'improv_style_bpm'"), ("on_change", "on_improv_style_jam_setting_change"), ("persist_state", "'session'"), ("step", "1"))),
    "improv_groove": ("selectbox", ("'Groove intensity'", "list(GROOVE_INTENSITY)"), (("key", "'improv_groove'"), ("on_change", "on_improv_style_jam_setting_change"), ("persist_state", "'session'"))),
    "improv_style_prompt": ("text_input", ("'Describe your jam (optional)'",), (("key", "'improv_style_prompt'"), ("placeholder", "'e.g. medium jazz-funk progression in D minor'"))),
    "improv_gen_style": ("button", ("'Generate progression'",), (("args", "(session_state,)"), ("key", "'improv_gen_style'"), ("on_click", "_queue_style_jam_generation_intent"), ("type", "'primary'"))),
    "improv_ensemble": ("selectbox", ("'Ensemble'", "list(jam_ensembles())"), (("key", "'improv_ensemble'"), ("on_change", "on_improv_jam_setting_change"), ("persist_state", "'session'"))),
    "improv_jam_style": ("selectbox", ("'Groove style'", "list(STYLE_JAM_STYLES)"), (("key", "'improv_jam_style'"), ("on_change", "on_improv_jam_setting_change"), ("persist_state", "'session'"))),
    "improv_jam_difficulty": ("selectbox", ("'Difficulty'", "list(DIFFICULTY_LEVELS)"), (("format_func", "level_label"), ("key", "'improv_jam_difficulty'"), ("on_change", "on_improv_jam_setting_change"), ("persist_state", "'session'"))),
    "improv_jam_key": ("selectbox", ("'Concert Key'", "_jam_key_opts"), (("format_func", "display_key_label"), ("key", "'improv_jam_key'"), ("on_change", "on_improv_jam_key_change"), ("persist_state", "'session'"))),
    "improv_jam_bpm": ("slider", ("'Tempo'", "70", "180"), (("key", "'improv_jam_bpm'"), ("on_change", "on_improv_jam_setting_change"), ("persist_state", "'session'"), ("step", "1"))),
    "improv_jam_mood": ("selectbox", ("'Atmosphere'", "list(MOOD_OPTIONS)"), (("key", "'improv_jam_mood'"), ("on_change", "on_improv_jam_setting_change"), ("persist_state", "'session'"))),
    "improv_jam_intensity": ("selectbox", ("'Groove intensity'", "list(GROOVE_INTENSITY)"), (("key", "'improv_jam_intensity'"), ("on_change", "on_improv_jam_setting_change"), ("persist_state", "'session'"))),
    "improv_gen_jam": ("button", ("'Generate jam session'",), (("args", "(session_state,)"), ("key", "'improv_gen_jam'"), ("on_click", "_queue_jam_session_generation_intent"), ("type", "'primary'"))),
}
# Creation order on dev 3587e435 (Style Jam, then the Generator).
JAM_WIDGET_ORDER_BEFORE = list(JAM_WIDGETS_BEFORE)


def _function(name: str) -> ast.FunctionDef:
    tree = ast.parse(UI.read_text(encoding="utf-8"))
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


def _jam_widgets() -> tuple[list[str], dict[str, tuple]]:
    calls = []
    for node in ast.walk(_function("_tab_entry_modes")):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        kw = {k.arg: k.value for k in node.keywords}
        key = kw.get("key")
        if not (isinstance(key, ast.Constant) and key.value in JAM_WIDGETS_BEFORE):
            continue
        sig = (
            node.func.attr,
            tuple(ast.unparse(a) for a in node.args),
            tuple(sorted((k, ast.unparse(v)) for k, v in kw.items())),
        )
        calls.append((node.lineno, key.value, sig))
    calls.sort()
    return [c[1] for c in calls], {c[1]: c[2] for c in calls}


def _branch_source(marker: str, end_marker: str) -> str:
    src = ast.get_source_segment(UI.read_text(encoding="utf-8"), _function("_tab_entry_modes")) or ""
    start = src.index(marker)
    return src[start : src.index(end_marker, start)] if end_marker else src[start:]


def _split_selectors(group: str) -> list[str]:
    """Split a selector list on top-level commas (``:where(a,b)`` stays whole)."""
    out, depth, cur = [], 0, ""
    for ch in group:
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    out.append(cur.strip())
    return [s for s in out if s]


class JamWidgetsUnchangedTests(unittest.TestCase):
    def test_every_jam_widget_keeps_key_label_options_callback_and_args(self) -> None:
        _, sigs = _jam_widgets()
        self.assertEqual(sigs, JAM_WIDGETS_BEFORE)

    def test_jam_widgets_are_created_in_the_same_order(self) -> None:
        order, _ = _jam_widgets()
        self.assertEqual(order, JAM_WIDGET_ORDER_BEFORE)

    def test_open_in_backing_row_is_unchanged_and_shared(self) -> None:
        src = ast.get_source_segment(UI.read_text(encoding="utf-8"), _function("_render_open_practice_backing_row")) or ""
        self.assertIn('jam_key = "improv_to_backing_jam" if workflow == "jam" else "improv_to_backing"', src)
        self.assertIn("on_click=on_open_backing,", src)


class StyleJamCardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.src = _branch_source('elif entry == "Style Jam Mode":', "\n    else:\n")

    def test_the_card_and_its_groups_are_keyed_containers(self) -> None:
        self.assertIn("st.container(key=jam_art.STYLE_JAM_CARD)", self.src)
        self.assertIn('st.container(key="improv_style_jam_controls")', self.src)  # phone density CSS hook
        self.assertIn("st.container(key=jam_art.STYLE_JAM_ACTIONS)", self.src)
        self.assertIn("st.container(key=jam_art.STYLE_JAM_RESULT)", self.src)
        self.assertIn('st.container(key=f"{jam_art.STYLE_JAM_SECTION_PREFIX}{_sec_i}")', self.src)
        self.assertIn("jam_art.jam_cards_css()", self.src)
        self.assertIn('jam_art.hero_html(\n                    "style_jam"', self.src)

    def test_generated_panel_reads_only_style_jams_own_sections(self) -> None:
        self.assertIn('gen = session_state.get("improv_generated_sections")', self.src)
        self.assertIn("sections=gen,", self.src)
        self.assertIn("for _sec_i, (sec, chs) in enumerate(gen.items()):", self.src)
        self.assertIn("jam_art.section_head_html(sec, _shown.get(sec, chs), _sec_i)", self.src)  # _shown: gen in guitar shapes
        self.assertIn("render_creative_progression_block(st, session_state, {sec: chs})", self.src)
        for foreign in ("improv_jam_session", "song_data", "preview_sections", "improv_ctx"):
            self.assertNotIn(foreign, self.src)

    def test_the_green_success_banner_is_replaced_by_the_description(self) -> None:
        self.assertNotIn("st.success(", self.src)
        self.assertIn("jam_art.style_jam_summary(", self.src)


class GeneratorCardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.src = _branch_source('from jam_control_ownership import jam_ensembles, seed_jam_controls_before_mount', "")

    def test_the_card_band_and_groups_are_keyed_containers(self) -> None:
        self.assertIn("st.container(key=jam_art.GENERATOR_CARD)", self.src)
        self.assertIn("st.container(key=jam_art.GENERATOR_BAND)", self.src)
        self.assertIn('st.container(key="improv_jam_gen_controls")', self.src)  # phone density CSS hook
        self.assertIn("st.container(key=jam_art.GENERATOR_ACTIONS)", self.src)
        self.assertIn("st.container(key=jam_art.GENERATOR_RESULT)", self.src)
        self.assertIn('st.container(key=f"{jam_art.GENERATOR_SECTION_PREFIX}{_sec_i}")', self.src)
        self.assertIn('jam_art.hero_html(\n                    "jam_generator"', self.src)
        self.assertIn("jam_art.lineup_html(str(ensemble or \"\"), str(session_state.get(\"improv_jam_style\") or \"\"))", self.src)

    def test_seeding_still_happens_before_any_generator_widget(self) -> None:
        seed = self.src.index('seed_jam_controls_before_mount(session_state, "jam_session_generator")')
        self.assertLess(seed, self.src.index('key="improv_ensemble"'))
        self.assertLess(seed, self.src.index("jam_art.hero_html("))

    def test_generated_panel_reads_only_the_generators_own_jam(self) -> None:
        self.assertIn('jam = session_state.get("improv_jam_session")', self.src)
        self.assertIn('_jam_sections = jam.get("sections") or {}', self.src)
        self.assertIn("sections=_jam_sections,", self.src)
        self.assertIn("for _sec_i, (sec, chs) in enumerate(_jam_sections.items()):", self.src)
        self.assertIn("jam_art.generator_summary(jam, key_label=_jam_key_label)", self.src)
        for foreign in ("improv_generated_sections", "song_data", "preview_sections", "improv_ctx"):
            self.assertNotIn(foreign, self.src)


class CssScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.css = jam_art.jam_cards_css()

    def test_one_style_tag_on_one_line(self) -> None:
        self.assertTrue(self.css.startswith("<style>") and self.css.endswith("</style>"))
        self.assertNotIn("\n", self.css)
        self.assertEqual(self.css.count("{"), self.css.count("}"))

    def test_every_rule_is_scoped_to_a_jam_card_container(self) -> None:
        body = self.css[len("<style>") : -len("</style>")]
        groups = re.findall(r"([^{}]+)\{[^{}]*\}", body)
        self.assertGreater(len(groups), 40)
        for group in groups:
            for sel in _split_selectors(group):
                self.assertRegex(sel, r"^(\.block-container )?(\.st-key-jam_card_|\[class\*=\"st-key-jam_card_)", sel)

    def test_no_external_resources(self) -> None:
        for bad in ("@import", "url(", "http:", "https:", "font-family"):
            self.assertNotIn(bad, self.css)

    def test_both_cards_set_their_own_surface_and_ink(self) -> None:
        for key in (jam_art.STYLE_JAM_CARD, jam_art.GENERATOR_CARD):
            rule = re.search(r"\.st-key-" + key + r"\{([^}]*)\}", self.css)
            self.assertIsNotNone(rule, key)
            self.assertIn("--jc-ink:", rule.group(1))
            self.assertIn("background:", rule.group(1))
        self.assertIn("#f0f9ff", self.css)  # Style Jam: light blue
        self.assertIn("#0e1a3d", self.css)  # Generator: dark blue
        # Widget labels follow the card's ink, beating the global label colour.
        self.assertIn(f'.block-container .st-key-{jam_art.STYLE_JAM_CARD} label[data-testid="stWidgetLabel"] p', self.css)

    def test_phone_layout_block(self) -> None:
        self.assertIn(f"@media (max-width:{jam_art.PHONE_MAX_WIDTH_PX}px)", self.css)
        self.assertEqual(jam_art.PHONE_MAX_WIDTH_PX, 640)


class ArtworkTests(unittest.TestCase):
    def test_artwork_files_are_self_contained_svg(self) -> None:
        ids: dict[str, set[str]] = {}
        for name in jam_art.ART_NAMES:
            path = jam_art.ART_DIR / f"{name}.svg"
            text = path.read_text(encoding="utf-8")
            root = ET.fromstring(text)
            self.assertTrue(root.tag.endswith("svg"), name)
            self.assertEqual(root.get("viewBox"), "0 0 960 300")
            for bad in ("<image", "<script", "href", "<foreignObject", "@import", "url(http"):
                self.assertNotIn(bad, text, f"{name}: {bad}")
            self.assertEqual(re.findall(r"https?://[^\"']+", text), ["http://www.w3.org/2000/svg"])
            ids[name] = set(re.findall(r'id="([^"]+)"', text))
        self.assertTrue(all(i.startswith("sj-") for i in ids["style_jam"]))
        self.assertTrue(all(i.startswith("jg-") for i in ids["jam_generator"]))

    def test_inline_artwork_is_one_line_without_comments(self) -> None:
        for name in jam_art.ART_NAMES:
            svg = jam_art.artwork_svg(name)
            self.assertTrue(svg.startswith("<svg") and svg.endswith("</svg>"))
            self.assertNotIn("\n", svg)
            self.assertNotIn("<!--", svg)
        with self.assertRaises(ValueError):
            jam_art.artwork_svg("../secrets")


class HelperTests(unittest.TestCase):
    SECTIONS = {"A": ["Dm7", "G7", "Cmaj7", ""], "B": ["Em7", "A7"], "Outro": ["Dm7", "G7", "C6"]}

    def test_arrangement_form_keeps_order_and_drops_blanks(self) -> None:
        form = jam_art.arrangement_form(self.SECTIONS)
        self.assertEqual([n for n, _ in form], ["A", "B", "Outro"])
        self.assertEqual(form[0][1], ["Dm7", "G7", "Cmaj7"])
        self.assertEqual(jam_art.arrangement_form(None), [])

    def test_style_jam_summary(self) -> None:
        out = jam_art.style_jam_summary(
            self.SECTIONS, style="Bossa Nova", key_label="F major", mood="Mellow",
            difficulty="Intermediate", groove="Medium", bpm=120,
        )
        self.assertEqual(out["title"], "Bossa Nova in F major")
        self.assertEqual(
            out["line"],
            "A mellow, intermediate Bossa Nova progression at 120 BPM with a medium groove "
            "— 3 sections, 8 chords: A → B → Outro.",
        )
        one = jam_art.style_jam_summary({"A": ["C"]}, style="", key_label="C", mood="", difficulty="", groove="", bpm="x")
        self.assertEqual(one["line"], "A Style jam progression — 1 section, 1 chord: A.")

    def test_generator_summary_uses_only_the_jam_record(self) -> None:
        jam = {"title": "Dark Funk — Rock trio", "ensemble": "Rock trio", "style": "Funk", "key": "Eb",
               "bpm": 104, "atmosphere": "late-night", "sections": self.SECTIONS}
        out = jam_art.generator_summary(jam, key_label=lambda k: f"{k} major")
        self.assertEqual(out["title"], "Dark Funk — Rock trio")
        self.assertEqual(
            out["line"],
            "Rock trio · in Eb major · Funk · ~104 BPM · late-night — 3 sections, 8 chords.",
        )
        self.assertEqual(jam_art.generator_summary({})["title"], "Jam session")

    def test_section_head_shows_the_generated_chords_escaped(self) -> None:
        out = jam_art.section_head_html("A <x>", ["Dm7", "G7", "<b>"], 5)
        self.assertIn("jc-tone-1", out)  # tones cycle
        self.assertIn('<span class="jc-sec-badge">A &lt;x&gt;</span>', out)
        self.assertIn("3 chords", out)
        self.assertEqual(re.findall(r'<span class="jc-chord">([^<]*)</span>', out), ["Dm7", "G7", "&lt;b&gt;"])

    def test_result_head_has_a_proportional_form_strip(self) -> None:
        out = jam_art.result_head_html(kicker="K", title="T", line="L", sections=self.SECTIONS)
        self.assertIn('aria-label="Song structure: A → B → Outro"', out)
        self.assertEqual(re.findall(r"flex:(\d+) 1 0", out), ["3", "2", "3"])
        self.assertNotIn("jc-form", jam_art.result_head_html(kicker="K", title="T", line="L", sections={}))

    def test_hero_html(self) -> None:
        out = jam_art.hero_html("style_jam", kicker="K", title="T & co", line="L", chips=(("Style", "Funk"), ("Tempo", "")))
        self.assertIn("<svg", out)
        self.assertIn("T &amp; co", out)
        self.assertIn("Funk", out)
        self.assertEqual(out.count('class="jc-chip"'), 1)  # empty values are left out
        self.assertNotIn("\n", out)

    def test_every_ensemble_has_its_real_lineup(self) -> None:
        from backing_performance_plan import ENSEMBLES
        from jam_control_ownership import JAM_ENSEMBLES

        for name in JAM_ENSEMBLES:
            playing, later = jam_art.ensemble_lineup(name)
            self.assertEqual(len(playing), len(ENSEMBLES[name].roles), name)
            self.assertEqual(len(later), len(ENSEMBLES[name].missing), name)
        self.assertEqual([n for _, n in jam_art.ensemble_lineup("Rock trio")[0]], ["Electric guitar", "Bass", "Drums"])
        # Its written horn: the instrument the horns branch records ("Tenor sax"), or the role's wording without it.
        self.assertIn([n for _, n in jam_art.ensemble_lineup("Jazz quartet")[1]], (["Sax / trumpet"], ["Tenor sax"]))
        self.assertEqual(jam_art.ensemble_lineup("Kazoo choir"), ((), ()))

    def test_lineup_html_names_members_not_yet_in_the_backing(self) -> None:
        out = jam_art.lineup_html("Latin quartet")
        self.assertIn("Piano", out)
        self.assertIn("Not in the backing yet: Latin percussion", out)
        self.assertNotIn("Not in the backing yet", jam_art.lineup_html("Jazz trio"))
        self.assertIn("Kazoo choir", jam_art.lineup_html("Kazoo choir"))


if __name__ == "__main__":
    unittest.main()


def test_banner_chips_only_name_a_value_the_control_shows():
    """A Song-Based seed ("Song Default") is not a Style Jam style: the banner must not show it as the style."""
    import jam_card_art as jca
    from improvisation_intelligence import STYLE_JAM_STYLES

    assert jca.shown_option("Bossa Nova", STYLE_JAM_STYLES) == "Bossa Nova"
    assert jca.shown_option("Song Default", STYLE_JAM_STYLES) == ""
    assert jca.shown_option(None, STYLE_JAM_STYLES) == ""
    html = jca.hero_html("style_jam", kicker="k", title="t", line="l",
                         chips=(("Style", jca.shown_option("Song Default", STYLE_JAM_STYLES)), ("Tempo", "100 BPM")))
    assert "Song Default" not in html and "100 BPM" in html



def test_lineup_follows_what_the_engine_will_play(monkeypatch):
    """With the jam's groove the line-up is the performance plan: no guitar shown where none can play."""
    import jam_card_art as jca

    monkeypatch.delenv("MUSIC_ROCK_GUITAR", raising=False)
    playing, later = jca.ensemble_lineup("Rock trio", "Bossa Nova")
    names = [n for _, n in playing]
    assert "Electric guitar" not in names and "Guitar" not in names
    assert any("uitar" in n for _, n in later)  # named as not available, never as playing
    written, _ = jca.ensemble_lineup("Rock trio")
    assert [n for _, n in written] == ["Electric guitar", "Bass", "Drums"]  # without a groove: the written line-up
    assert jca.ensemble_lineup("Jazz quartet", "Jazz Swing")[1]  # the horn is still not available on this branch


def test_lineup_names_each_horn_the_engine_plays(monkeypatch):
    """A plan that plays horns names them by instrument (trumpet, tenor sax), never one "Horn" for two players."""
    import types

    import backing_performance_plan as pp
    import jam_card_art as jca

    spec = types.SimpleNamespace(roles=("keys", "bass", "drums"), missing=("horns",), horns=("trumpet", "tenor"))
    monkeypatch.setitem(pp.ENSEMBLES, "Test quintet", spec)
    playing = types.SimpleNamespace(roles=("keys", "horns", "bass", "drums"), unavailable=(), horns=("trumpet", "tenor"))
    monkeypatch.setattr(pp, "resolve_performance_plan", lambda **k: playing)
    names = [n for _, n in jca.ensemble_lineup("Test quintet", "Jazz Swing")[0]]
    assert names == ["Keys", "Trumpet", "Tenor sax", "Bass", "Drums"]
    monkeypatch.setitem(pp.ENSEMBLES, "Jazz quintet", spec)
    names = [n for _, n in jca.ensemble_lineup("Jazz quintet", "Jazz Swing")[0]]
    assert names == ["Piano", "Trumpet", "Tenor sax", "Upright bass", "Drums"]  # the jazz wording, like the trio
    html = jca.lineup_html("Test quintet", "Jazz Swing")
    assert "Trumpet" in html and "Tenor sax" in html and "Not in the backing yet" not in html
    silent = types.SimpleNamespace(roles=("keys", "bass", "drums"), unavailable=("horns",), horns=())
    monkeypatch.setattr(pp, "resolve_performance_plan", lambda **k: silent)
    playing_now, later = jca.ensemble_lineup("Test quintet", "Jazz Swing")
    assert "Trumpet" not in [n for _, n in playing_now]
    assert [n for _, n in later] == ["Trumpet", "Tenor sax"]  # named as not available, never as playing
