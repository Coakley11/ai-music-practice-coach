# -*- coding: utf-8 -*-
"""One-shot patch: Multitrack icons/labels + mobile Back/Forward placement."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "streamlit_music_practice_app.py"


def main() -> None:
    text = APP.read_text(encoding="utf-8")

    old1 = '    section_open_fn(st, "Song / project", icon="🎵")'
    new1 = (
        '    section_open_fn(\n'
        '        st,\n'
        '        "Song / section",\n'
        '        icon=FEATURE_ICONS.get("section_focus") or "🔁",\n'
        '    )'
    )
    if old1 not in text:
        raise SystemExit("Song/project call site not found")
    text = text.replace(old1, new1, 1)

    old2 = (
        "            for slot in MT_SLOTS:\n"
        "                _slot_ready = bool(st.session_state.mt_tracks.get(slot))\n"
        "                st.markdown(\n"
        '                    f"**{html.escape(slot)}** {multitrack_layer_badge_html(ready=_slot_ready)}",\n'
        "                    unsafe_allow_html=True,\n"
        "                )"
    )
    new2 = (
        "            for slot in MT_SLOTS:\n"
        "                _slot_ready = bool(st.session_state.mt_tracks.get(slot))\n"
        "                try:\n"
        "                    from music_feature_icons import format_icon_html, instrument_icon\n"
        "\n"
        "                    _layer_ico = format_icon_html(instrument_icon(slot))\n"
        "                except Exception:\n"
        '                    _layer_ico = "✨"\n'
        "                st.markdown(\n"
        "                    f'<p class=\"ui-mt-layer-heading\">'\n"
        "                    f'<span class=\"ui-mt-layer-ico\" aria-hidden=\"true\">{_layer_ico}</span>'\n"
        "                    f'<span>{html.escape(slot)}</span> '\n"
        "                    f'{multitrack_layer_badge_html(ready=_slot_ready)}</p>',\n"
        "                    unsafe_allow_html=True,\n"
        "                )"
    )
    if old2 not in text:
        raise SystemExit("layer heading loop not found")
    text = text.replace(old2, new2, 1)

    old_early = (
        "try:\n"
        "    render_floating_nav_history(st, st.session_state, rerun_fn=st.rerun)\n"
        "except Exception as _early_nav_hist_exc:\n"
        "    if _developer_mode_enabled():\n"
        '        st.warning(f"Back/Forward nav render failed: {_early_nav_hist_exc}")\n'
    )
    new_early = (
        "# Back/Forward render moved below restore welcome / above quick-nav.\n"
        "# Desktop still uses fixed gutter placement via CSS + pin script.\n"
    )
    if old_early not in text:
        raise SystemExit("early nav history render not found")
    text = text.replace(old_early, new_early, 1)

    old_qn = (
        "if pp.show_quick_nav(st):\n"
        "    _quick_nav_page_before = _studio_page\n"
        "    _studio_page = render_page_quick_nav(\n"
    )
    new_qn = (
        "# Persistent Back/Forward — below restore welcome, above quick-nav grid.\n"
        "# Phone: in-flow compact row. Desktop: fixed mid-viewport gutter (unchanged).\n"
        "try:\n"
        '    with st.container(key="studio_history_nav_row"):\n'
        "        render_floating_nav_history(st, st.session_state, rerun_fn=st.rerun)\n"
        "except Exception as _hist_nav_exc:\n"
        "    if _developer_mode_enabled():\n"
        '        st.warning(f"Back/Forward nav render failed: {_hist_nav_exc}")\n'
        "\n"
        "if pp.show_quick_nav(st):\n"
        "    _quick_nav_page_before = _studio_page\n"
        "    _studio_page = render_page_quick_nav(\n"
    )
    if old_qn not in text:
        raise SystemExit("quick nav block not found")
    text = text.replace(old_qn, new_qn, 1)

    APP.write_text(text, encoding="utf-8")
    check = APP.read_text(encoding="utf-8")
    assert "Song / section" in check
    assert 'icon="🎵"' not in check or check.count('section_open_fn') >= 1
    assert "Song / project" not in check
    assert "ui-mt-layer-heading" in check
    assert "studio_history_nav_row" in check
    assert check.count("render_floating_nav_history(st, st.session_state, rerun_fn=st.rerun)") == 1
    print("OK: streamlit_music_practice_app.py patched")


if __name__ == "__main__":
    main()
