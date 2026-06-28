"""Audio channel extraction + gain control for mic streamer."""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkProcessingMetrics:
    raw_rms: float
    processed_rms: float
    peak: float
    clipping_ratio: float
    gate_active: bool
    agc_gain: float


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
    pcm_data, updated_gain, _metrics = apply_agc_and_gate_with_metrics(
        mono=mono,
        current_gain=current_gain,
        noise_gate_rms=noise_gate_rms,
        target_rms=target_rms,
        min_gain=min_gain,
        max_gain=max_gain,
        agc_attack=agc_attack,
        agc_release=agc_release,
    )
    return pcm_data, updated_gain


def apply_agc_and_gate_with_metrics(
    mono: np.ndarray,
    current_gain: float,
    noise_gate_rms: float,
    target_rms: float,
    min_gain: float,
    max_gain: float,
    agc_attack: float,
    agc_release: float,
) -> tuple[bytes, float, ChunkProcessingMetrics]:
    mono_f = mono.astype(np.float32) / 2147483648.0
    mono_f = mono_f - float(np.mean(mono_f))
    rms = float(np.sqrt(np.mean(np.square(mono_f))))
    gate_active = rms < noise_gate_rms

    if gate_active:
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

    processed = np.clip(mono_f, -1.0, 1.0)
    peak = float(np.max(np.abs(processed))) if processed.size else 0.0
    clipping_ratio = float(np.mean(np.abs(processed) >= 0.99)) if processed.size else 0.0
    processed_rms = float(np.sqrt(np.mean(np.square(processed)))) if processed.size else 0.0
    pcm_data = np.clip(processed * 32767.0, -32768, 32767).astype(np.int16).tobytes()
    metrics = ChunkProcessingMetrics(
        raw_rms=rms,
        processed_rms=processed_rms,
        peak=peak,
        clipping_ratio=clipping_ratio,
        gate_active=gate_active,
        agc_gain=current_gain,
    )
    return pcm_data, current_gain, metrics
