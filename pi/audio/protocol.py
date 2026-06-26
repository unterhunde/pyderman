"""UDP wire format for audio streaming."""

from __future__ import annotations

import struct

AUDIO_HEADER = struct.Struct("!IH")

