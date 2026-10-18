"""Musician-friendly microphone capture for the Mission recorder (single-chord and span).

``st.audio_input`` asks the browser for ``{audio: {sampleRate: {ideal: 16000}}}`` and nothing
else, so Chrome / Edge apply their *speech-call* processing to the microphone by default:
echo cancellation, noise suppression and automatic gain control. Noise suppression treats a
held, steady tone (a sustained flute note) as background noise and pulls it down; AGC pumps
the level between loud and quiet phrases. That happens before MediaRecorder ever sees the
audio, so no later stage can bring it back.

Streamlit exposes no constraint option, so the Mission recorder installs a small page script
that, **only for a recording started from a Mission recorder's Record button**, adds
``echoCancellation / noiseSuppression / autoGainControl: false`` (and ``voiceIsolation:
false`` where the browser has it) to that one ``getUserMedia`` call. The values are plain
(non-required) constraints: a browser that does not support one ignores it, and an
``OverconstrainedError`` falls back to the original request. Every other microphone in the
app (Upload Analysis, Multitrack, tuner, Composition) keeps its current behaviour.

The script also leaves a small diagnostic on ``window.__mcMusicCapture`` (requested
constraints, the settings the track actually got, Record → Stop wall-clock time) so a take's
capture can be checked against its decoded duration.
"""

from __future__ import annotations

import json
from typing import Any

MUSIC_CAPTURE_CONSTRAINTS: dict[str, bool] = {
    "echoCancellation": False,
    "noiseSuppression": False,
    "autoGainControl": False,
}
# A Record click arms music capture for the getUserMedia call that follows it.
ARM_WINDOW_MS = 4000
SCRIPT_VERSION = 1

_SCRIPT = r"""
<script>
(function () {
  var w = window.parent && window.parent.document ? window.parent : window;
  var d = w.document, md = w.navigator && w.navigator.mediaDevices;
  if (!md || !md.getUserMedia) return;
  var state = w.__mcMusicCapture = w.__mcMusicCapture || {version: __VERSION__, keys: [], armedAt: 0, takes: []};
  __KEYS__.forEach(function (k) { if (state.keys.indexOf(k) < 0) state.keys.push(k); });

  function missionMicFor(el) {
    for (var n = el; n && n !== d; n = n.parentElement) {
      if (!n.classList) continue;
      for (var i = 0; i < state.keys.length; i++) {
        if (n.classList.contains('st-key-' + state.keys[i])) return state.keys[i];
      }
    }
    return null;
  }

  if (!d.__mcMusicCaptureListener) {
    d.__mcMusicCaptureListener = true;
    d.addEventListener('click', function (ev) {
      var btn = ev.target && ev.target.closest && ev.target.closest('[data-testid="stAudioInputActionButton"]');
      if (!btn) return;
      var key = missionMicFor(btn);
      if (!key) return;
      var label = (btn.getAttribute('aria-label') || '').trim();
      if (/^stop/i.test(label)) {  // "Stop recording" — check before "Record"
        var t = state.takes.length ? state.takes[state.takes.length - 1] : null;
        if (t && t.key === key && !t.stoppedAt) { t.stoppedAt = Date.now(); t.wallSec = (t.stoppedAt - t.startedAt) / 1000; }
      } else if (/^record$/i.test(label)) {
        state.armedAt = Date.now(); state.armedKey = key;
      }
    }, true);
  }

  if (!md.__mcMusicCapturePatched) {
    md.__mcMusicCapturePatched = true;
    var original = md.getUserMedia.bind(md);
    md.getUserMedia = function (c) {
      var armed = state.armedAt && (Date.now() - state.armedAt) < __WINDOW__ && c && c.audio;
      if (!armed) return original(c);
      state.armedAt = 0;
      var audio = (typeof c.audio === 'object' && c.audio) ? Object.assign({}, c.audio) : {};
      var music = __CONSTRAINTS__;
      var sup = md.getSupportedConstraints ? md.getSupportedConstraints() : {};
      Object.keys(music).forEach(function (k) { if (sup[k] !== false) audio[k] = music[k]; });
      if (sup.voiceIsolation) audio.voiceIsolation = false;
      var take = {key: state.armedKey, requested: audio, startedAt: Date.now(), mode: 'music'};
      state.takes.push(take); if (state.takes.length > 20) state.takes.shift();
      var req = Object.assign({}, c, {audio: audio});
      return original(req).then(function (stream) {
        try {
          var tr = stream.getAudioTracks()[0];
          take.settings = tr.getSettings(); take.device = tr.label;
        } catch (e) {}
        return stream;
      }, function (err) {
        if (err && (err.name === 'OverconstrainedError' || err.name === 'NotReadableError')) {
          take.mode = 'fallback:' + err.name;
          return original(c);
        }
        throw err;
      });
    };
  }
})();
</script>
"""


def music_capture_script(mic_keys: list[str]) -> str:
    """The page script for these Mission recorder mic widget keys."""
    return (
        _SCRIPT.replace("__KEYS__", json.dumps(list(mic_keys)))
        .replace("__CONSTRAINTS__", json.dumps(MUSIC_CAPTURE_CONSTRAINTS))
        .replace("__WINDOW__", str(ARM_WINDOW_MS))
        .replace("__VERSION__", str(SCRIPT_VERSION))
    )


def render_music_capture_mode(st: Any, *, mic_key: str) -> bool:
    """Install music capture for the Mission recorder whose ``st.audio_input`` key is ``mic_key``."""
    html = getattr(st, "html", None)
    if html is None:
        return False
    try:
        html(music_capture_script([mic_key]), unsafe_allow_javascript=True)
    except TypeError:  # an older Streamlit without script support: browser defaults remain
        return False
    return True


__all__ = [
    "ARM_WINDOW_MS",
    "MUSIC_CAPTURE_CONSTRAINTS",
    "music_capture_script",
    "render_music_capture_mode",
]
