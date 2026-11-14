"""What the Multitrack recorder was asked to play along with, and what happened to it.

Issue 77A. A layer's recorder refuses to arm unless every asset it was asked to play along with -
the generated monitor backing and each monitored layer - has been fetched and decoded by the
browser. That guarantee is right: recording against parts the player cannot hear, while the take is
aligned as though they could, is worse than not recording. What was wrong is everything around it.

Three separate failures all reached the musician as one sentence, "One of the parts to play along
with could not be loaded", with no way to tell which part or what to do:

1. **The expected duration was a prediction, and the renderer could never match it.** Python sent
   ``len(events) * bar_seconds * loops`` while ``synthesize_chords_to_numpy`` leaves a full second
   of decay after the music, every time, at every loop count. The component rejects anything more
   than 0.6 s from the prediction, so **every** prepared backing was refused - measured 16.0 s
   predicted against 17.0 s rendered, 32.0 against 33.0, 48.0 against 49.0.
2. **The prediction also counted the wrong bars**: the estimate counts the chart on screen, while
   Prepare backing renders from the canonical concert sections, which can be a different length
   (72 bars predicted against 78 rendered on a real song: 78 x 2 x 60*4/82 + 1.0 = 457.585 s, the
   exact figure the recorder reported).
3. **A monitored layer whose bytes are not decodable audio** blocks every *other* layer, because one
   failed asset fails the whole request. The layer that owns the bad audio is the only one that can
   still record, since a layer never monitors itself.

So the duration handed to the recorder is now **measured from the asset's own bytes**
(:func:`wav_duration_sec`), and the recorder's acknowledgement - which already carries the asset id,
byte count, content type and error - is kept instead of discarded, so the page can name the part
and say what to do about it.

Nothing here renders, decodes or re-times audio: it reads a WAV header, remembers an
acknowledgement, and writes English. Pure functions, no Streamlit import.
"""

from __future__ import annotations

import struct
from typing import Any, Iterable, Mapping, MutableMapping

#: Per-slot store of the recorder's last acknowledgement.
ACK_KEY = "_mt_recorder_asset_ack"

#: Monitors the musician has explicitly chosen to record without, per slot being recorded.
EXCLUDED_KEY = "_mt_monitors_excluded"

#: Bumped to make the component re-fetch and re-decode its assets ("Try again").
RETRY_KEY = "_mt_monitor_retry_nonce"

#: The asset id the component uses for the generated monitor backing.
BACKING_ASSET_ID = "backing"

#: Prefix of the asset id for a monitored layer: ``layer:<slot>``.
LAYER_ASSET_PREFIX = "layer:"

_ACK_FIELDS = (
    "fp",
    "nonce",
    "state",
    "attempts",
    "error",
    "bytes",
    "mime",
    "sample_rate",
    "channels",
    "duration_sec",
    "expected_duration_sec",
    "assets",
    "instance",
    "failed_asset",
)


# --------------------------------------------------------------------------------------------
# 1. The honest duration
# --------------------------------------------------------------------------------------------
def wav_duration_sec(data: Any) -> float | None:
    """Seconds of audio in a RIFF/WAVE byte string, or ``None`` when it cannot be read.

    Read from the header rather than estimated, because the estimate is what broke recording. Walks
    the chunk list instead of assuming a canonical 44-byte header: a WAV written by another tool can
    carry ``LIST``/``fact``/``JUNK`` chunks before ``data``, and rejecting those would reject valid
    recordings.

    When the declared ``data`` size runs past the end of the bytes (a truncated upload), the bytes
    that are actually present are used, so the answer describes the audio in hand.
    """
    if not isinstance(data, (bytes, bytearray, memoryview)):
        return None
    raw = bytes(data)
    if len(raw) < 12 or raw[0:4] != b"RIFF" or raw[8:12] != b"WAVE":
        return None
    sample_rate = 0
    channels = 0
    bits = 0
    block_align = 0
    data_bytes: int | None = None
    pos = 12
    while pos + 8 <= len(raw):
        chunk_id = raw[pos:pos + 4]
        try:
            (size,) = struct.unpack("<I", raw[pos + 4:pos + 8])
        except struct.error:
            break
        body = pos + 8
        if chunk_id == b"fmt " and body + 16 <= len(raw):
            try:
                _fmt, channels, sample_rate, _byte_rate, block_align, bits = struct.unpack(
                    "<HHIIHH", raw[body:body + 16]
                )
            except struct.error:
                return None
        elif chunk_id == b"data":
            available = max(0, len(raw) - body)
            data_bytes = min(int(size), available) if size else available
        pos = body + int(size) + (int(size) % 2)
        if size == 0 and chunk_id not in (b"fmt ", b"data"):
            break
    if not sample_rate or data_bytes is None:
        return None
    frame = block_align or (max(1, channels) * max(1, bits // 8))
    if frame <= 0:
        return None
    frames = data_bytes // frame
    if frames <= 0:
        return 0.0
    return float(frames) / float(sample_rate)


def backing_duration_for_recorder(
    monitor_wav: Any,
    fallback_sec: Any = 0.0,
) -> float:
    """The duration to tell the recorder to expect for this exact backing asset.

    Measured from the bytes the recorder will fetch. The fallback is used only when the bytes cannot
    be read as WAV at all, and even then it is the previous behaviour rather than a new failure.
    """
    measured = wav_duration_sec(monitor_wav)
    if measured is not None and measured > 0:
        return float(measured)
    try:
        return max(0.0, float(fallback_sec or 0.0))
    except (TypeError, ValueError):
        return 0.0


# --------------------------------------------------------------------------------------------
# 2. Keeping the acknowledgement
# --------------------------------------------------------------------------------------------
def record_layer_recorder_ack(
    session_state: MutableMapping[str, Any],
    slot: str,
    ack: Any,
) -> bool:
    """Remember what this slot's recorder said about loading its assets. True when it was kept.

    The component sends this on every load outcome, for its own fingerprint and load request. It was
    being dropped on the floor by ``render_layer_recorder``, which returns early for any value
    without a take - which is why a failure could never be explained.
    """
    if not isinstance(ack, Mapping):
        return False
    state = str(ack.get("state") or "")
    if state not in ("loading", "ready", "failed"):
        return False
    kept: dict[str, Any] = {k: ack.get(k) for k in _ACK_FIELDS}
    kept["state"] = state
    trace = ack.get("trace")
    kept["trace"] = list(trace)[-16:] if isinstance(trace, (list, tuple)) else []
    if not kept.get("failed_asset"):
        kept["failed_asset"] = _failed_asset_from_trace(kept["trace"])
    store = session_state.get(ACK_KEY)
    if not isinstance(store, dict):
        store = {}
        session_state[ACK_KEY] = store
    store[str(slot)] = kept
    return True


def _failed_asset_from_trace(trace: Iterable[Any]) -> str:
    """The asset id the component was working on when it gave up.

    Older component builds do not send ``failed_asset`` at the top level, but every attempt is
    traced with the asset it concerned, so the id is recoverable from the last failing step.
    """
    found = ""
    for entry in trace or ():
        if not isinstance(entry, Mapping):
            continue
        step = str(entry.get("step") or "")
        asset = str(entry.get("asset") or "")
        if asset and step in ("failed", "attempt_failed"):
            found = asset
    return found


def layer_recorder_ack(session_state: Mapping[str, Any], slot: str) -> dict[str, Any]:
    store = session_state.get(ACK_KEY)
    if isinstance(store, Mapping) and isinstance(store.get(slot), Mapping):
        return dict(store[slot])
    return {}


def asset_load_failed(session_state: Mapping[str, Any], slot: str) -> bool:
    return str(layer_recorder_ack(session_state, slot).get("state") or "") == "failed"


# --------------------------------------------------------------------------------------------
# 3. Saying which part, in the musician's words
# --------------------------------------------------------------------------------------------
def asset_slot(asset_id: Any) -> str:
    """The layer slot an asset id refers to, or "" for the backing / an unknown id."""
    text = str(asset_id or "")
    if text.startswith(LAYER_ASSET_PREFIX):
        return text[len(LAYER_ASSET_PREFIX):]
    return ""


def asset_label(
    asset_id: Any,
    session_state: Mapping[str, Any] | None = None,
    *,
    default: str = "one of the parts to play along with",
) -> str:
    """What to call this asset on screen: the backing, or a layer by the name the musician gave it."""
    text = str(asset_id or "").strip()
    if not text:
        return default
    if text == BACKING_ASSET_ID:
        return "the generated backing track"
    slot = asset_slot(text)
    if slot:
        name = ""
        if isinstance(session_state, Mapping):
            name = str(session_state.get(f"mt_name_{slot}") or "").strip()
        return f"your {name or slot} layer"
    return default


def _duration_phrase(ack: Mapping[str, Any]) -> str:
    decoded = ack.get("duration_sec")
    expected = ack.get("expected_duration_sec")
    try:
        d = float(decoded)
        e = float(expected)
    except (TypeError, ValueError):
        return ""
    if d <= 0 or e <= 0:
        return ""
    return f"its audio is {d:.1f} seconds long but this project expected {e:.1f} seconds"


def monitor_failure_message(
    session_state: Mapping[str, Any],
    slot: str,
    *,
    excluded_any: bool = False,
) -> str:
    """One plain sentence naming the part that failed and what the musician can do.

    Deliberately not the raw exception: "Unable to decode audio data" and
    "decoded 457.59 s, expected 421.46 s" are what the browser said, not what a musician can act on.
    The technical detail is kept for the diagnostics panel, not used as the message.
    """
    ack = layer_recorder_ack(session_state, slot)
    if str(ack.get("state") or "") != "failed":
        return ""
    who = asset_label(ack.get("failed_asset"), session_state)
    error = str(ack.get("error") or "").lower()
    duration = _duration_phrase(ack)
    if duration and ("expected" in error or "decoded" in error):
        why = duration
        what = (
            "Prepare the backing again so it matches this project"
            if asset_slot(ack.get("failed_asset")) == "" and str(ack.get("failed_asset") or "") == BACKING_ASSET_ID
            else "Record that layer again"
        )
    elif "decode" in error:
        why = "its audio could not be played by this browser"
        what = (
            "Prepare the backing again"
            if str(ack.get("failed_asset") or "") == BACKING_ASSET_ID
            else "Record or upload that layer again"
        )
    elif "http" in error or "fetch" in error or "abort" in error:
        why = "it could not be fetched from the app"
        what = "Try again"
    else:
        why = "it could not be loaded"
        what = "Try again"
    tail = (
        " Recording is held back so a take can never be aligned against parts you did not hear."
        if not excluded_any
        else ""
    )
    return f"**Recording is unavailable:** {who} could not be loaded — {why}. {what}, or record without that part.{tail}"


def failure_detail(session_state: Mapping[str, Any], slot: str) -> str:
    """The exact technical line, for a diagnostics expander rather than the main message."""
    ack = layer_recorder_ack(session_state, slot)
    if not ack:
        return ""
    bits = [
        f"asset={ack.get('failed_asset') or '(not reported)'}",
        f"state={ack.get('state')}",
        f"attempts={ack.get('attempts')}",
        f"bytes={ack.get('bytes')}",
        f"type={ack.get('mime')}",
        f"decoded_sec={ack.get('duration_sec')}",
        f"expected_sec={ack.get('expected_duration_sec')}",
        f"error={ack.get('error')}",
    ]
    return " · ".join(str(b) for b in bits)


# --------------------------------------------------------------------------------------------
# 4. Recovering: try again, or record without that part
# --------------------------------------------------------------------------------------------
def retry_nonce(session_state: Mapping[str, Any]) -> int:
    try:
        return int(session_state.get(RETRY_KEY) or 0)
    except (TypeError, ValueError):
        return 0


def request_retry(session_state: MutableMapping[str, Any]) -> int:
    """Ask every recorder to fetch and decode its assets again."""
    nonce = retry_nonce(session_state) + 1
    session_state[RETRY_KEY] = nonce
    return nonce


def excluded_monitors(session_state: Mapping[str, Any]) -> set[str]:
    raw = session_state.get(EXCLUDED_KEY)
    if isinstance(raw, (set, frozenset)):
        return {str(x) for x in raw}
    if isinstance(raw, (list, tuple)):
        return {str(x) for x in raw}
    return set()


def monitor_is_excluded(session_state: Mapping[str, Any], slot: str) -> bool:
    return str(slot) in excluded_monitors(session_state)


def exclude_monitor(session_state: MutableMapping[str, Any], slot: str) -> set[str]:
    """Record without this part.

    The slot is removed from the recorder's **request**, not merely silenced during playback: the
    take's ``monitors_expected`` then matches what actually started, so ``sync_state`` keeps telling
    the truth about whether the take is aligned. Silencing it at playback time would leave a take
    that claims to have been recorded against a part nobody heard.
    """
    current = excluded_monitors(session_state)
    current.add(str(slot))
    session_state[EXCLUDED_KEY] = sorted(current)
    request_retry(session_state)
    return current


def include_monitor(session_state: MutableMapping[str, Any], slot: str) -> set[str]:
    current = excluded_monitors(session_state)
    current.discard(str(slot))
    session_state[EXCLUDED_KEY] = sorted(current)
    request_retry(session_state)
    return current


def clear_monitor_exclusions(session_state: MutableMapping[str, Any]) -> None:
    session_state[EXCLUDED_KEY] = []


def excluded_notice(session_state: Mapping[str, Any]) -> str:
    """What the musician is recording without, said out loud rather than silently applied."""
    names = [
        asset_label(f"{LAYER_ASSET_PREFIX}{slot}", session_state)
        for slot in sorted(excluded_monitors(session_state))
    ]
    if not names:
        return ""
    if len(names) == 1:
        listed = names[0]
    else:
        listed = ", ".join(names[:-1]) + " and " + names[-1]
    return (
        f"Recording without {listed}. That part will not play while you record and the take is "
        "measured against what actually played."
    )


__all__ = [
    "ACK_KEY",
    "BACKING_ASSET_ID",
    "EXCLUDED_KEY",
    "LAYER_ASSET_PREFIX",
    "RETRY_KEY",
    "asset_label",
    "asset_load_failed",
    "asset_slot",
    "backing_duration_for_recorder",
    "clear_monitor_exclusions",
    "exclude_monitor",
    "excluded_monitors",
    "excluded_notice",
    "failure_detail",
    "include_monitor",
    "layer_recorder_ack",
    "monitor_failure_message",
    "monitor_is_excluded",
    "record_layer_recorder_ack",
    "request_retry",
    "retry_nonce",
    "wav_duration_sec",
]
