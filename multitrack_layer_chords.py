"""Per-layer chord progression for the Multitrack recording workspace.

Several musicians can record different instruments into one Multitrack session, so each recording layer
carries its *own* chord representation while the backing stays in concert pitch:

* a flute / piano / voice layer reads the concert chords (C minor stays Cm);
* an alto or tenor saxophone layer reads its written chords (concert Cm shows as Am for alto);
* a guitar layer can read capo shapes when Capo Shape Mode is on.

The audio is never touched: ``concert_bar_chords`` is the one sounding progression, and every layer label
is a projection of it. The same ``effective_practice_context`` / ``instrument_transposition`` /
``guitar_capo`` mechanisms the rest of the app uses do the projecting - there is no second key system here.

Pure Python: no Streamlit import, so the timeline and the labels are unit-testable.
"""

from __future__ import annotations

import html
import json
from typing import Any, Iterable, Mapping, Sequence

LAYER_INSTRUMENT_KEY_PREFIX = "mt_layer_instrument_"
LAYER_CHORDS_SHOWN_KEY_PREFIX = "mt_layer_chords_on_"

# Instruments a layer can be charted for. Concert-pitch instruments read the sounding chords; the
# transposing ones read their written chords.
CONCERT_INSTRUMENTS: tuple[str, ...] = (
    "Piano",
    "Guitar",
    "Bass",
    "Voice",
    "Flute",
    "Violin",
    "Drums",
)
WRITTEN_INSTRUMENTS: tuple[str, ...] = (
    "Alto saxophone (Eb)",
    "Tenor saxophone (Bb)",
    "Soprano saxophone (Bb)",
    "Baritone saxophone (Eb)",
    "Bb Trumpet",
    "Bb Clarinet",
)

# Which instrument a fresh layer is charted for, from the canonical slot names.
_SLOT_DEFAULT_INSTRUMENT: dict[str, str] = {
    "Guitar": "Guitar",
    "Bass": "Bass",
    "Piano / Keys": "Piano",
    "Vocals": "Voice",
    "Sax / winds": "Alto saxophone (Eb)",
    "Extra layer": "Piano",
}


def layer_instrument_options() -> list[str]:
    """Every instrument a Multitrack layer can be charted for (concert first, then written)."""
    return list(CONCERT_INSTRUMENTS) + list(WRITTEN_INSTRUMENTS)


def default_layer_instrument(slot: str, session_state: Mapping[str, Any] | None = None) -> str:
    """Default chart instrument for a slot.

    A "Sax / winds" layer follows the saxophone type the musician already picked in their practice
    setup, so the Multitrack chart matches the charts they read everywhere else.
    """
    slot = str(slot or "").strip()
    base = _SLOT_DEFAULT_INSTRUMENT.get(slot, "Piano")
    if slot == "Sax / winds" and session_state is not None:
        try:
            from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY

            picked = str(session_state.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or "").strip()
        except ImportError:
            picked = ""
        if picked in WRITTEN_INSTRUMENTS:
            return picked
    return base


def layer_instrument(
    session_state: Mapping[str, Any] | None,
    slot: str,
) -> str:
    """The instrument this layer is charted for (the musician's pick, else the slot default)."""
    if session_state is not None:
        chosen = str(session_state.get(f"{LAYER_INSTRUMENT_KEY_PREFIX}{slot}") or "").strip()
        if chosen in layer_instrument_options():
            return chosen
    return default_layer_instrument(slot, session_state)


def layer_chart_key(
    concert_key: str,
    instrument: str,
    session_state: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    """``(chart key, mode)`` for one layer: ``concert``, ``written`` or ``shape``.

    Transposing instruments always read their written key here. On the Multitrack page each layer is a
    different player, so one layer reading written charts must not depend on (or change) the global
    written-chart checkbox, which belongs to the single musician at the Practice page.
    """
    concert = str(concert_key or "C").strip() or "C"
    inst = str(instrument or "").strip()
    if inst == "Guitar" and session_state is not None:
        try:
            from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY, shape_chart_key_for_concert

            if session_state.get(CAPO_ENABLED_KEY):
                shape = str(session_state.get(CAPO_SHAPE_KEY) or "").strip()
                if shape:
                    return str(shape_chart_key_for_concert(concert, shape) or concert), "shape"
        except ImportError:
            pass
    try:
        from instrument_transposition import TRANSPOSING_SEMITONE_STEPS, written_key_for_type

        if TRANSPOSING_SEMITONE_STEPS.get(inst):
            return str(written_key_for_type(concert, inst) or concert), "written"
    except ImportError:
        pass
    return concert, "concert"


def layer_key_label(concert_key: str, instrument: str, session_state: Mapping[str, Any] | None = None) -> str:
    """Explicit, unambiguous key wording for the layer header."""
    chart, mode = layer_chart_key(concert_key, instrument, session_state)
    if mode == "written":
        return f"Written key: {chart}"
    if mode == "shape":
        return f"Shape key: {chart}"
    return f"Concert key: {chart}"


def project_chords_for_layer(
    concert_chords: Sequence[str],
    *,
    concert_key: str,
    instrument: str,
    session_state: Mapping[str, Any] | None = None,
) -> list[str]:
    """Concert chords as this layer's player reads them (identity for concert-pitch instruments)."""
    chords = [str(c or "").strip() for c in concert_chords]
    chart, mode = layer_chart_key(concert_key, instrument, session_state)
    if mode == "concert" or not chart or chart == concert_key:
        return chords
    try:
        from effective_practice_context import musician_facing_chord
    except ImportError:
        return chords
    out = []
    for chord in chords:
        if not chord:
            out.append(chord)
            continue
        try:
            out.append(str(musician_facing_chord(chord, concert_key=concert_key, chart_key=chart) or chord))
        except Exception:
            out.append(chord)
    return out


def concert_bar_chords(
    session_state: Mapping[str, Any] | None,
    *,
    chart_sections: Mapping[str, Sequence[str]] | None = None,
    selected_sections: Iterable[str] = (),
    section_names: Sequence[str] | None = None,
    chart_key: str = "",
    concert_key: str = "",
) -> list[str]:
    """One sounding (concert) chord per bar for the selected Multitrack range.

    The Practice chart the Multitrack page already holds is in the *chart* key (written key, or a capo
    shape key), so it cannot be used for audio or as the base for per-layer projection. The canonical
    concert sections are preferred; when they are unavailable the chart sections are un-projected by the
    distance between the two keys.
    """
    chosen = [str(n) for n in (selected_sections or []) if str(n).strip()]
    sections: Mapping[str, Sequence[str]] | None = None
    if session_state is not None:
        try:
            from improvisation_motif import concert_song_sections_from_session

            resolved = concert_song_sections_from_session(dict(session_state))
            if isinstance(resolved, dict) and resolved:
                sections = resolved
        except Exception:
            sections = None
    unproject = sections is None
    if sections is None:
        sections = chart_sections or {}

    ordered: list[tuple[str, Sequence[str]]] = []
    try:
        from songs.form import section_order

        ordered = list(section_order(dict(sections), section_names=list(section_names) if section_names else None))
    except Exception:
        ordered = list(sections.items())

    bars: list[str] = []
    for name, chords in ordered:
        if chosen and str(name) not in chosen:
            continue
        bars.extend(str(c or "").strip() for c in (chords or []))

    if unproject and bars:
        bars = _unproject_to_concert(bars, chart_key=chart_key, concert_key=concert_key)
    return bars


def _unproject_to_concert(chords: Sequence[str], *, chart_key: str, concert_key: str) -> list[str]:
    """Undo a chart (written / shape) projection so the chords sound as written in the concert key."""
    chart = str(chart_key or "").strip()
    concert = str(concert_key or "").strip()
    if not chart or not concert or chart == concert:
        return [str(c) for c in chords]
    try:
        from effective_practice_context import musician_facing_chord
    except ImportError:
        return [str(c) for c in chords]
    out = []
    for chord in chords:
        chord = str(chord or "")
        if not chord:
            out.append(chord)
            continue
        try:
            out.append(str(musician_facing_chord(chord, concert_key=chart, chart_key=concert) or chord))
        except Exception:
            out.append(chord)
    return out


def concert_sections_for_backing(
    session_state: Mapping[str, Any] | None,
    chart_sections: Mapping[str, Sequence[str]] | None,
    *,
    chart_key: str = "",
    concert_key: str = "",
) -> dict[str, list[str]]:
    """The section map the Multitrack monitor backing must be rendered from: sounding (concert) chords.

    The page's own chart is in the written / shape key whenever the musician reads transposed charts, and
    rendering audio straight from it made the monitor backing sound in the written key.
    """
    sections: Mapping[str, Sequence[str]] | None = None
    if session_state is not None:
        try:
            from improvisation_motif import concert_song_sections_from_session

            resolved = concert_song_sections_from_session(dict(session_state))
            if isinstance(resolved, dict) and resolved:
                sections = resolved
        except Exception:
            sections = None
    if sections is not None:
        return {str(k): [str(c) for c in (v or [])] for k, v in sections.items()}
    base = chart_sections or {}
    return {
        str(k): _unproject_to_concert(list(v or []), chart_key=chart_key, concert_key=concert_key)
        for k, v in base.items()
    }


def layer_chord_timeline(
    chords: Sequence[str],
    *,
    bar_duration: float,
    loops: int = 1,
    count_in_sec: float = 0.0,
) -> list[dict[str, Any]]:
    """One cell per played bar: ``{chord, start, end, bar, pass}`` in seconds from the count-in start.

    ``start``/``end`` already include the count-in, so a cell's window matches the transport clock the
    musician hears; nothing is highlighted while the count-in is still running.
    """
    cells: list[dict[str, Any]] = []
    bar_duration = float(bar_duration or 0.0)
    if bar_duration <= 0 or not chords:
        return cells
    passes = max(1, int(loops or 1))
    offset = max(0.0, float(count_in_sec or 0.0))
    index = 0
    for pass_no in range(passes):
        for bar_no, chord in enumerate(chords):
            start = offset + index * bar_duration
            cells.append(
                {
                    "chord": str(chord or ""),
                    "start": round(start, 4),
                    "end": round(start + bar_duration, 4),
                    "bar": bar_no + 1,
                    "pass": pass_no + 1,
                }
            )
            index += 1
    return cells


def chord_index_at(cells: Sequence[Mapping[str, Any]], seconds: float) -> int:
    """Index of the cell sounding at ``seconds``, or -1 before the first / after the last."""
    t = float(seconds)
    for i, cell in enumerate(cells):
        if float(cell["start"]) <= t < float(cell["end"]):
            return i
    return -1


def layer_chord_strip_html(
    cells: Sequence[Mapping[str, Any]],
    *,
    layer_id: str,
    key_label: str,
    instrument: str,
    clock_key: str = "__mtClock",
) -> str:
    """Compact, scrollable chord strip that follows the Multitrack transport clock.

    The transport component publishes ``window.parent[clock_key]`` ( ``{t, playing}`` , seconds from the
    count-in start). This strip only *reads* that clock, so it never advances while playback is stopped
    or paused, and it follows count-in, loops and restarts exactly as the transport does.
    """
    cells_json = json.dumps([{"c": c["chord"], "s": c["start"], "e": c["end"], "b": c["bar"]} for c in cells])
    safe_id = "".join(ch if ch.isalnum() else "_" for ch in str(layer_id))[:60] or "layer"
    chips = "".join(
        f'<span class="mtc-cell" data-i="{i}" title="Bar {html.escape(str(c["bar"]))}">'
        f'{html.escape(str(c["chord"]) or "–")}</span>'
        for i, c in enumerate(cells)
    )
    return f"""
<div class="mtc-wrap" id="mtc-{safe_id}" data-mt-layer-chords="2026-11-03-v1">
  <style>
    .mtc-wrap {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }}
    .mtc-head {{ display:flex; flex-wrap:wrap; gap:6px; align-items:baseline;
                 font-size:0.74rem; font-weight:700; color:#475569; margin-bottom:5px; }}
    .mtc-head .mtc-key {{ color:#b45309; }}
    .mtc-strip {{ display:flex; gap:5px; overflow-x:auto; padding:5px 2px 7px 2px;
                  scrollbar-width:thin; -webkit-overflow-scrolling:touch; }}
    .mtc-cell {{ flex:0 0 auto; min-width:46px; padding:7px 9px; border-radius:9px; text-align:center;
                 border:1px solid #e2e8f0; background:#fff; color:#0f172a;
                 font-size:0.82rem; font-weight:700; font-variant-numeric:tabular-nums;
                 transition: background-color .12s linear, color .12s linear, transform .12s linear; }}
    .mtc-cell.current {{ background:linear-gradient(135deg,#f59e0b,#ea580c); color:#fff;
                         border-color:#c2410c; transform:translateY(-1px);
                         box-shadow:0 3px 10px rgba(234,88,12,0.32); }}
    .mtc-none {{ color:#94a3b8; font-size:0.76rem; }}
    @media (max-width: 420px) {{ .mtc-cell {{ min-width:40px; padding:6px 7px; font-size:0.78rem; }} }}
  </style>
  <div class="mtc-head">
    <span>{html.escape(str(instrument))}</span>
    <span class="mtc-key">{html.escape(str(key_label))}</span>
    <span id="mtc-state-{safe_id}" class="mtc-none">waiting for transport</span>
  </div>
  <div class="mtc-strip" id="mtc-strip-{safe_id}">{chips or '<span class="mtc-none">No chords in the selected range.</span>'}</div>
  <script>
    (function () {{
      const cells = {cells_json};
      const strip = document.getElementById("mtc-strip-{safe_id}");
      const state = document.getElementById("mtc-state-{safe_id}");
      const chips = Array.from(strip.querySelectorAll(".mtc-cell"));
      let shown = -2;

      function clock() {{
        try {{ return window.parent ? window.parent["{clock_key}"] : null; }} catch (e) {{ return null; }}
      }}

      function indexAt(t) {{
        for (let i = 0; i < cells.length; i++) {{
          if (t >= cells[i].s && t < cells[i].e) return i;
        }}
        return -1;
      }}

      function paint() {{
        const c = clock();
        // No transport yet, or it is stopped/paused: hold the current highlight, never advance it.
        let idx = -1;
        if (c && c.playing) {{
          idx = indexAt(Number(c.t) || 0);
          state.textContent = idx < 0 ? "count-in" : ("bar " + cells[idx].b);
        }} else if (c) {{
          state.textContent = "paused";
          requestAnimationFrame(paint);
          return;
        }} else {{
          state.textContent = "press Play in the transport";
        }}
        if (idx !== shown) {{
          chips.forEach((el, i) => el.classList.toggle("current", i === idx));
          if (idx >= 0 && chips[idx]) {{
            const el = chips[idx];
            const left = el.offsetLeft - (strip.clientWidth - el.clientWidth) / 2;
            strip.scrollTo({{ left: Math.max(0, left), behavior: "smooth" }});
          }}
          shown = idx;
        }}
        requestAnimationFrame(paint);
      }}
      requestAnimationFrame(paint);
    }})();
  </script>
</div>
"""


def transport_clock_script(clock_key: str = "__mtClock") -> str:
    """JS the Multitrack transport runs so every layer strip can follow one clock.

    Publishes ``{t, playing}`` on the parent window: ``t`` is seconds from the count-in start (so it
    covers count-in, loops and restarts), ``playing`` is false whenever the transport is stopped.
    """
    return f"""
    function mtPublishClock(t, playing) {{
      try {{ window.parent["{clock_key}"] = {{ t: Number(t) || 0, playing: !!playing, at: Date.now() }}; }}
      catch (e) {{}}
    }}
    """


__all__ = [
    "CONCERT_INSTRUMENTS",
    "LAYER_CHORDS_SHOWN_KEY_PREFIX",
    "LAYER_INSTRUMENT_KEY_PREFIX",
    "WRITTEN_INSTRUMENTS",
    "chord_index_at",
    "concert_bar_chords",
    "concert_sections_for_backing",
    "default_layer_instrument",
    "layer_chart_key",
    "layer_chord_strip_html",
    "layer_chord_timeline",
    "layer_instrument",
    "layer_instrument_options",
    "layer_key_label",
    "project_chords_for_layer",
    "transport_clock_script",
]
