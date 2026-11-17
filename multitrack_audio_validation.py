"""Can this audio actually be played? Issue 77A.

A layer's bytes are fetched and decoded by the browser whenever another layer records against it, so
a file the app accepted but no decoder can read does not fail at upload time - it fails later, as
"One of the parts to play along with could not be loaded", on a *different* layer, naming nothing.
Measured: a 916-byte file named ``.wav`` was accepted as a take (the uploader checks the extension
and the landing path only rejects bytes under 512), and it then disabled Record on every other
layer.

So an upload is decoded here, once, before it becomes a layer.

Three rules this follows deliberately:

* **Decode; do not judge the container.** The check is whether a decoder can read it, never whether
  its sample rate, bit depth or container is one this app happens to prefer - a 22.05 kHz mono WAV
  or an m4a from a phone is perfectly valid and must not be turned away.
* **Never destroy.** This answers a question; it deletes nothing and replaces nothing. A layer that
  is already in a project stays exactly where it is even when it fails, and the caller reports the
  problem instead of silently fixing it.
* **Three answers, not two.** A file may be VERIFIED (a decoder read it), REJECTED (a decoder
  refused it), or UNVERIFIED (no decoder was available, so nothing was established). The first
  version of this module collapsed the third into the first - it returned "ok" with the reason
  buried in a string, which no caller could distinguish from a successful decode. Accepting an
  unchecked file is right, for legacy compatibility; telling the musician it will play is not. The
  two cases are now separate states, and an unverified file is adopted *and said to be unchecked*.
"""

from __future__ import annotations

import io
import os
import tempfile
from typing import Any

#: Anything smaller than this cannot be audio - a WAV header alone is 44 bytes.
MIN_AUDIO_BYTES = 512

#: A decoder read the audio. This is the only state that says anything about playability.
VERIFIED = "verified"

#: A decoder was available and refused the bytes.
REJECTED = "rejected"

#: No decoder was available, so nothing was established either way.
UNVERIFIED = "unverified"


class AudioCheck:
    """The verdict on one piece of audio: verified, rejected, or not checked at all."""

    __slots__ = ("status", "reason", "decoder", "duration_sec", "sample_rate", "channels")

    def __init__(
        self,
        status: str,
        reason: str = "",
        decoder: str = "",
        duration_sec: float | None = None,
        sample_rate: int | None = None,
        channels: int | None = None,
    ) -> None:
        self.status = str(status)
        self.reason = str(reason or "")
        self.decoder = str(decoder or "")
        self.duration_sec = duration_sec
        self.sample_rate = sample_rate
        self.channels = channels

    # --- the three states, asked separately so a caller cannot conflate two of them -------
    @property
    def verified(self) -> bool:
        """A decoder actually read this audio. The only basis for saying it will play."""
        return self.status == VERIFIED

    @property
    def rejected(self) -> bool:
        """A decoder refused it. Do not adopt it."""
        return self.status == REJECTED

    @property
    def unverified(self) -> bool:
        """Nothing was established - adopt it for compatibility, and say it was not checked."""
        return self.status == UNVERIFIED

    @property
    def ok(self) -> bool:
        """May this be adopted? True for verified AND unverified - never a claim about playback.

        Kept so the decision to accept reads naturally at the call site, but it deliberately does
        NOT answer "will this play": ``verified`` is the only property that does.
        """
        return not self.rejected

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return (
            f"AudioCheck(status={self.status!r}, decoder={self.decoder!r}, reason={self.reason!r}, "
            f"duration_sec={self.duration_sec}, sample_rate={self.sample_rate})"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "verified": self.verified,
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
            return AudioCheck(REJECTED, "the file contains no audio frames", "soundfile")
        return AudioCheck(VERIFIED, "", "soundfile", frames / float(rate), rate, channels)
    except Exception as exc:
        return AudioCheck(REJECTED, _short(exc), "soundfile")


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
            return AudioCheck(VERIFIED, "", "librosa", float(len(y)) / float(rate), int(rate), 1)
        return AudioCheck(REJECTED, "the file contains no audio frames", "librosa")
    except Exception as exc:
        return AudioCheck(REJECTED, _short(exc), "librosa")
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
        return AudioCheck(REJECTED, "there was no audio data", "")
    raw = bytes(data)
    if len(raw) < MIN_AUDIO_BYTES:
        return AudioCheck(REJECTED, f"the file is only {len(raw)} bytes long", "")
    suffix = ""
    name = str(filename or "")
    if "." in name:
        suffix = "." + name.rsplit(".", 1)[-1].lower()[:8]

    first = _try_soundfile(raw)
    if first is not None and first.verified:
        return first
    second = _try_librosa(raw, suffix)
    if second is not None and second.verified:
        return second
    # A decoder was available and refused it.
    if first is not None or second is not None:
        failed = second if (second is not None and second.reason) else first
        reason = failed.reason if failed is not None else "it could not be decoded"
        decoder = failed.decoder if failed is not None else ""
        return AudioCheck(REJECTED, reason, decoder)
    # No decoder is installed. The file is still accepted - refusing every upload because a library
    # is missing would be worse than the defect - but this is NOT a successful decode, and the
    # caller must not present it as one.
    return AudioCheck(
        UNVERIFIED,
        "no audio decoder is available on this device, so the file could not be checked",
        "",
    )


#: Sources whose bytes were captured here rather than chosen from a file.
RECORDED_SOURCES = frozenset({"shared-clock", "basic-recorder"})


def rejection_message(
    check: AudioCheck, filename: str = "", *, layer_name: str = "", source: str = "upload"
) -> str:
    """What to tell the musician when a take cannot be used, without blaming their playing.

    The advice depends on where the take came from. "Export it again and upload it" is right for a
    file and wrong for something that was just recorded here - the musician has no file to export,
    and the honest instruction is to record it again.
    """
    where = f" The {layer_name} layer is unchanged." if layer_name else ""
    detail = check.reason or "it could not be decoded"
    if str(source or "") in RECORDED_SOURCES:
        return (
            f"**That recording could not be read as audio** — {detail}. Nothing was changed."
            + where
            + " It was not kept, so it cannot cause a problem later; please record it again."
        )
    who = str(filename or "that file").strip() or "that file"
    return (
        f"**{who} could not be added as a layer** — {detail}. Nothing was changed."
        + where
        + " Please export it again as WAV, MP3 or M4A and upload it once more."
    )


def unverified_notice(check: AudioCheck, filename: str = "") -> str:
    """What to say when a file was accepted without being checked.

    Not a success message. The file is kept, and the musician is told plainly that nothing has
    established it will play - because the browser is the thing that has to decode it while
    recording, and if it cannot, Record will be held back and will name this layer.
    """
    if not check.unverified:
        return ""
    who = str(filename or "that file").strip() or "that file"
    return (
        f"**{who} was added without being checked** — "
        + (check.reason or "no audio decoder is available on this device")
        + ". It may still turn out not to play while you record; if that happens, the recorder "
        "will say so and name this layer."
    )


__all__ = [
    "AudioCheck",
    "MIN_AUDIO_BYTES",
    "RECORDED_SOURCES",
    "REJECTED",
    "UNVERIFIED",
    "VERIFIED",
    "check_audio_bytes",
    "rejection_message",
    "unverified_notice",
]
