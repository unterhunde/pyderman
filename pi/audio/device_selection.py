"""Input audio device discovery and validation."""

from __future__ import annotations

import pyaudio


def select_input_device(pa: pyaudio.PyAudio, preferred_index: int | None) -> tuple[int, dict]:
    selected_device_index: int | None = preferred_index
    selected_device_info = None

    if selected_device_index is not None:
        selected_device_info = pa.get_device_info_by_index(selected_device_index)
    else:
        for idx in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(idx)
            name = str(info.get("name", "")).lower()
            max_in = int(info.get("maxInputChannels", 0))
            if max_in <= 0:
                continue
            if "google voicehat" in name or "(hw:0,0)" in name:
                selected_device_index = idx
                selected_device_info = info
                break

        if selected_device_info is None:
            default_idx = int(pa.get_default_input_device_info()["index"])
            selected_device_index = default_idx
            selected_device_info = pa.get_device_info_by_index(default_idx)

    if selected_device_info is None or selected_device_index is None:
        raise RuntimeError("No usable input audio device found.")

    return selected_device_index, selected_device_info

