"""Audio streamer configuration constants."""

from __future__ import annotations

import pyaudio

INPUT_CHANNELS = 2
OUTPUT_CHANNELS = 1
FORMAT = pyaudio.paInt32
CHUNK_FRAMES = 1024
INPUT_DEVICE_INDEX = 0
CHANNEL_MODE = "left"
NOISE_GATE_RMS = 0.003
TARGET_RMS = 0.070
MIN_GAIN = 1.0
MAX_GAIN = 20.0
AGC_ATTACK = 0.35
AGC_RELEASE = 0.15  # Increased from 0.05 - faster gain recovery for weak signals
