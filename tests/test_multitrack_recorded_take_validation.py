"""A recorded take is decoded before it becomes a layer, exactly as an upload is.

Recorded takes used to get a size check only - anything over 512 bytes was adopted - while
``check_audio_bytes`` ran for uploads alone, on the grounds that "this app wrote those bytes
itself". It did not, quite: the recorder encodes the take in browser JavaScript and carries it back
to Python, so a capture glitch or a truncated transfer can leave more than 512 bytes that no decoder
reads. Adopted as a layer, that becomes "its audio could not be played by this browser" on the NEXT
layer, and Record is held back for every other part.

These pin the two halves: the validator really does catch what the size guard lets through, and the
app now applies it to every source rather than to uploads only.
"""

from __future__ import annotations

import io
import math
import struct
import sys
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import multitrack_audio_validation as mav  # noqa: E402

APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")


def recorder_wav(seconds: float = 1.0, sr: int = 48000) -> bytes:
    """A take shaped like the shared-clock recorder's: 16-bit mono PCM in a RIFF container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        frames = b"".join(
            struct.pack("<h", int(6000 * math.sin(2 * math.pi * 440 * i / sr)))
            for i in range(int(seconds * sr)))
        w.writeframes(frames)
    return buf.getvalue()


class TheValidatorCatchesWhatSizeDoesNot(unittest.TestCase):
    def test_a_real_recorder_take_is_verified(self) -> None:
        check = mav.check_audio_bytes(recorder_wav(), "guitar-take.wav")
        if check.unverified:
            self.skipTest("no audio decoder installed here, so nothing can be verified")
        self.assertFalse(check.rejected, check.reason)

    def test_a_truncated_take_over_512_bytes_is_rejected(self) -> None:
        """What a dropped transfer leaves: a RIFF header that promises frames that are not there.

        The size guard adopts this - it is well over 512 bytes - and that is the whole defect.
        """
        good = recorder_wav()
        broken = good[:44] + b"\x00" * 0 + good[44:44]  # header only
        broken = broken + b"\xff" * 600                   # garbage where the frames should be
        broken = b"RIFX" + broken[4:]                      # and a container no decoder knows
        self.assertGreater(len(broken), mav.MIN_AUDIO_BYTES, "the size guard would adopt it")
        check = mav.check_audio_bytes(broken, "guitar-take.wav")
        if check.unverified:
            self.skipTest("no audio decoder installed here, so nothing can be rejected either")
        self.assertTrue(check.rejected, "an undecodable take must not become a layer")

    def test_text_that_merely_has_a_wav_name_is_rejected(self) -> None:
        """The stubs found in a real workspace: 'guitar' saved as track.wav, padded past 512."""
        stub = b"guitar" * 200
        self.assertGreater(len(stub), mav.MIN_AUDIO_BYTES)
        check = mav.check_audio_bytes(stub, "track-1.wav")
        if check.unverified:
            self.skipTest("no audio decoder installed here")
        self.assertTrue(check.rejected)


class EveryLandedTakeIsChecked(unittest.TestCase):
    def test_the_app_no_longer_validates_uploads_only(self) -> None:
        self.assertNotIn('_mt_landed_bytes is not None and _mt_landed_source == "upload":', APP,
                         "validation must not be restricted to uploads")
        self.assertIn("if _mt_landed_bytes is not None and _mt_landed_source:", APP)

    def test_the_rejection_is_worded_for_where_the_take_came_from(self) -> None:
        check = mav.AudioCheck(mav.REJECTED, "it could not be decoded", "soundfile")
        recorded = mav.rejection_message(check, "guitar-take.wav", layer_name="Guitar",
                                         source="shared-clock")
        uploaded = mav.rejection_message(check, "guitar.mp3", layer_name="Guitar",
                                         source="upload")
        self.assertIn("record it again", recorded)
        self.assertNotIn("upload it once more", recorded,
                         "a musician who just recorded has no file to export and upload")
        self.assertIn("upload it once more", uploaded)
        for text in (recorded, uploaded):
            self.assertIn("Nothing was changed", text)
            self.assertIn("Guitar layer is unchanged", text)

    def test_the_call_site_passes_the_source(self) -> None:
        self.assertIn("source=_mt_landed_source,", APP)


if __name__ == "__main__":
    unittest.main()
