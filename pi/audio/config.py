"""Audio streamer configuration constants."""

from __future__ import annotations

import pyaudio

INPUT_CHANNELS = 2
OUTPUT_CHANNELS = 1
FORMAT = pyaudio.paInt32
CHUNK_FRAMES = 1024
INPUT_DEVICE_INDEX = None
CHANNEL_MODE = "left"
NOISE_GATE_RMS = 0.0005  # Lowered from 0.003 - allow weak signals to pass through
TARGET_RMS = 0.080
MIN_GAIN = 1.0
MAX_GAIN = 28.0
AGC_ATTACK = 0.35
AGC_RELEASE = 0.15  # Increased from 0.05 - faster gain recovery for weak signals

