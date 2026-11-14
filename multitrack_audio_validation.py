"""Can this audio actually be played? Issue 77A.

A layer's bytes are fetched and decoded by the browser whenever another layer records against it, so
a file the app accepted but no decoder can read does not fail at upload time - it fails later, as
"One of the parts to play along with could not be loaded", on a *different* layer, naming nothing.
Measured: a 916-byte file named ``.wav`` was accepted as a take (the uploader checks the extension
and the landing path only rejects bytes under 512), and it then disabled Record on every other
layer.

So an upload is decoded here, once, before it becomes a layer.

Three rules this follows deliberately:

* **Fail open.** If no decoder is installed, the audio is accepted. Refusing everything because a
  library is missing would be worse than the defect.
* **Decode; do not judge the container.** The check is whether a decoder can read it, never whether
  its sample rate, bit depth or container is one this app happens to prefer - a 22.05 kHz mono WAV
  or an m4a from a phone is perfectly valid and must not be turned away.
* **Never destroy.** This answers a question; it deletes nothing and replaces nothing. A layer that
  is already in a project stays exactly where it is even when it fails, and the caller reports the
  problem instead of silently fixing it.
"""

from __future__ import annotations

import io
import os
import tempfile
from typing import Any

#: Anything smaller than this cannot be audio - a WAV header alone is 44 bytes.
MIN_AUDIO_BYTES = 512


class AudioCheck:
    """The verdict on one piece of audio."""

    __slots__ = ("ok", "reason", "decoder", "duration_sec", "sample_rate", "channels")

    def __init__(
        self,
        ok: bool,
        reason: str = "",
        decoder: str = "",
        duration_sec: float | None = None,
        sample_rate: int | None = None,
        channels: int | None = None,
    ) -> None:
        self.ok = bool(ok)
        self.reason = str(reason or "")
        self.decoder = str(decoder or "")
        self.duration_sec = duration_sec
        self.sample_rate = sample_rate
        self.channels = channels

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return (
            f"AudioCheck(ok={self.ok}, decoder={self.decoder!r}, reason={self.reason!r}, "
            f"duration_sec={self.duration_sec}, sample_rate={self.sample_rate})"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reason": self.reason,
            "decoder": self.decoder,
            "duration_sec": self.duration_sec,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
        }


def _try_soundfile(data: bytes) -> AudioCheck | None:
    try:
        import soundfile as sf
    except Exception:
        return None
    try:
        with sf.SoundFile(io.BytesIO(data)) as handle:
            frames = int(len(handle))
            rate = int(handle.samplerate or 0)
            channels = int(handle.channels or 0)
        if rate <= 0 or frames <= 0:
            return AudioCheck(False, "the file contains no audio frames", "soundfile")
        return AudioCheck(True, "", "soundfile", frames / float(rate), rate, channels)
    except Exception as exc:
        return AudioCheck(False, _short(exc), "soundfile")


def _try_librosa(data: bytes, suffix: str) -> AudioCheck | None:
    """Second opinion for containers soundfile cannot open (mp3/m4a/mp4/mov)."""
    try:
        import librosa
    except Exception:
        return None
    path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix or ".bin") as tmp:
            tmp.write(data)
            path = tmp.name
        y, rate = librosa.load(path, sr=None, mono=True)
        if rate and len(y):
            return AudioCheck(True, "", "librosa", float(len(y)) / float(rate), int(rate), 1)
        return AudioCheck(False, "the file contains no audio frames", "librosa")
    except Exception as exc:
        return AudioCheck(False, _short(exc), "librosa")
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


def _short(exc: Any, limit: int = 120) -> str:
    text = str(exc or "").strip().replace("\n", " ")
    return text[:limit] if text else exc.__class__.__name__


def check_audio_bytes(data: Any, filename: str = "") -> AudioCheck:
    """Whether a decoder on this machine can read these bytes as audio.

    Tries ``soundfile`` first (WAV/FLAC/OGG and friends), then ``librosa`` for the compressed
    containers the uploader also accepts. A failure from one decoder is not a verdict while another
    is still worth asking.
    """
    if not isinstance(data, (bytes, bytearray, memoryview)):
        return AudioCheck(False, "there was no audio data", "")
    raw = bytes(data)
    if len(raw) < MIN_AUDIO_BYTES:
        return AudioCheck(False, f"the file is only {len(raw)} bytes long", "")
    suffix = ""
    name = str(filename or "")
    if "." in name:
        suffix = "." + name.rsplit(".", 1)[-1].lower()[:8]

    first = _try_soundfile(raw)
    if first is not None and first.ok:
        return first
    second = _try_librosa(raw, suffix)
    if second is not None and second.ok:
        return second
    # Both available decoders refused it.
    if first is not None or second is not None:
        failed = second if (second is not None and second.reason) else first
        reason = failed.reason if failed is not None else "it could not be decoded"
        decoder = failed.decoder if failed is not None else ""
        return AudioCheck(False, reason, decoder)
    # Fail open: no decoder is installed, so this check cannot be the reason audio is refused.
    return AudioCheck(True, "no audio decoder is installed, so the file was not checked", "")


def rejection_message(check: AudioCheck, filename: str = "", *, layer_name: str = "") -> str:
    """What to tell the musician when an upload cannot be used, without blaming their playing."""
    who = str(filename or "that file").strip() or "that file"
    where = f" The {layer_name} layer is unchanged." if layer_name else ""
    detail = check.reason or "it could not be decoded"
    return (
        f"**{who} could not be added as a layer** — {detail}. Nothing was changed."
        + where
        + " Please export it again as WAV, MP3 or M4A and upload it once more."
    )


__all__ = [
    "AudioCheck",
    "MIN_AUDIO_BYTES",
    "check_audio_bytes",
    "rejection_message",
]
