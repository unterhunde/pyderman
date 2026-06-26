"""Audio channel extraction + gain control for mic streamer."""

from __future__ import annotations

import numpy as np


def select_mono_channel(samples: np.ndarray, input_channels: int, channel_mode: str, active_channel: int) -> tuple[np.ndarray, int]:
    if input_channels == 1:
        return samples, active_channel

    stereo = samples.reshape(-1, input_channels)
    if channel_mode == "left":
        return stereo[:, 0], active_channel
    if channel_mode == "right":
        return stereo[:, 1], active_channel
    if channel_mode == "mix":
        mixed = ((stereo[:, 0].astype(np.int64) + stereo[:, 1].astype(np.int64)) // 2).astype(np.int32)
        return mixed, active_channel

    left_rms = float(np.sqrt(np.mean(np.square(stereo[:, 0].astype(np.float32)))))
    right_rms = float(np.sqrt(np.mean(np.square(stereo[:, 1].astype(np.float32)))))
    stronger_channel = 0 if left_rms >= right_rms else 1
    stronger = max(left_rms, right_rms)
    weaker = min(left_rms, right_rms)
    if weaker == 0.0 or (stronger / weaker) > 1.2:
        active_channel = stronger_channel
    return stereo[:, active_channel], active_channel


def apply_agc_and_gate(
    mono: np.ndarray,
    current_gain: float,
    noise_gate_rms: float,
    target_rms: float,
    min_gain: float,
    max_gain: float,
    agc_attack: float,
    agc_release: float,
) -> tuple[bytes, float]:
    mono_f = mono.astype(np.float32) / 2147483648.0
    mono_f = mono_f - float(np.mean(mono_f))
    rms = float(np.sqrt(np.mean(np.square(mono_f))))

    if rms < noise_gate_rms:
        mono_f = mono_f * 0.18
        current_gain = max(min_gain, current_gain * (1.0 - (agc_release * 0.5)))
    else:
        desired_gain = np.clip(target_rms / (rms + 1e-7), min_gain, max_gain)
        if desired_gain > current_gain:
            current_gain += (desired_gain - current_gain) * agc_attack
        else:
            current_gain += (desired_gain - current_gain) * agc_release

        mono_f = mono_f * current_gain
        mono_f = np.tanh(mono_f * 2.0) / np.tanh(2.0)

    pcm_data = np.clip(mono_f * 32767.0, -32768, 32767).astype(np.int16).tobytes()
    return pcm_data, current_gain

