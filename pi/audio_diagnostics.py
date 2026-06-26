#!/usr/bin/env python3
"""Diagnose microphone signal levels on Raspberry Pi."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import numpy as np
import pyaudio

from pi.audio import config
from pi.audio.device_selection import select_input_device
from pi.audio.signal_processing import select_mono_channel, apply_agc_and_gate


def diagnose_audio():
    """Check microphone signal levels and gate behavior."""
    print("\n" + "=" * 80)
    print("AUDIO MICROPHONE DIAGNOSTICS")
    print("=" * 80 + "\n")
    
    pa = pyaudio.PyAudio()
    device_idx, device_info = select_input_device(pa, config.INPUT_DEVICE_INDEX)
    
    print(f"Device: {device_info.get('name')}")
    print(f"Index: {device_idx}")
    print(f"Max Input Channels: {device_info.get('maxInputChannels')}")
    print(f"Sample Rate: {int(device_info.get('defaultSampleRate'))} Hz")
    print()
    
    print("Configuration:")
    print(f"  Input Channels: {config.INPUT_CHANNELS}")
    print(f"  Output Channels: {config.OUTPUT_CHANNELS}")
    print(f"  Chunk Size: {config.CHUNK_FRAMES} frames")
    print(f"  Channel Mode: {config.CHANNEL_MODE}")
    print(f"  Noise Gate RMS: {config.NOISE_GATE_RMS} ← (threshold for signal suppression)")
    print(f"  Target RMS: {config.TARGET_RMS}")
    print(f"  AGC Attack: {config.AGC_ATTACK}")
    print(f"  AGC Release: {config.AGC_RELEASE}")
    print()
    
    stream = pa.open(
        format=config.FORMAT,
        channels=config.INPUT_CHANNELS,
        rate=int(device_info.get('defaultSampleRate')),
        input=True,
        input_device_index=device_idx,
        frames_per_buffer=config.CHUNK_FRAMES,
    )
    
    print("Listening for 5 seconds... (Speak into microphone)")
    print("-" * 80)
    
    max_rms = 0.0
    min_rms = float('inf')
    samples_read = 0
    suppressed_count = 0
    current_gain = 1.0
    
    try:
        for i in range(50):  # ~5 seconds at 1024 frames
            stereo_pcm = stream.read(config.CHUNK_FRAMES, exception_on_overflow=False)
            samples = np.frombuffer(stereo_pcm, dtype=np.int32)
            
            if samples.size != config.CHUNK_FRAMES * config.INPUT_CHANNELS:
                continue
            
            # Extract mono channel
            mono, _ = select_mono_channel(
                samples=samples,
                input_channels=config.INPUT_CHANNELS,
                channel_mode=config.CHANNEL_MODE,
                active_channel=0,
            )
            
            # Check RMS before signal processing
            mono_f = mono.astype(np.float32) / 2147483648.0
            mono_f = mono_f - float(np.mean(mono_f))
            rms = float(np.sqrt(np.mean(np.square(mono_f))))
            
            max_rms = max(max_rms, rms)
            if rms > 0:
                min_rms = min(min_rms, rms)
            
            samples_read += 1
            
            # Check if signal is being suppressed by noise gate
            if rms < config.NOISE_GATE_RMS:
                suppressed_count += 1
                status = "🔇 SUPPRESSED"
            else:
                status = "✓ PASSED"
            
            print(f"Chunk {i+1:2d}: RMS={rms:.6f}  Gain={current_gain:.2f}  {status}")
            
            # Apply processing
            pcm_data, current_gain = apply_agc_and_gate(
                mono=mono,
                current_gain=current_gain,
                noise_gate_rms=config.NOISE_GATE_RMS,
                target_rms=config.TARGET_RMS,
                min_gain=config.MIN_GAIN,
                max_gain=config.MAX_GAIN,
                agc_attack=config.AGC_ATTACK,
                agc_release=config.AGC_RELEASE,
            )
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()
    
    print("-" * 80)
    print()
    print("ANALYSIS:")
    print(f"  Max RMS observed: {max_rms:.6f}")
    print(f"  Min RMS observed: {min_rms:.6f}")
    print(f"  Noise gate threshold: {config.NOISE_GATE_RMS:.6f}")
    print(f"  Chunks suppressed: {suppressed_count}/{samples_read}")
    print()
    
    # Recommendations
    print("DIAGNOSTICS:")
    if max_rms < config.NOISE_GATE_RMS * 2:
        print("  ⚠️  PROBLEM: Microphone signal is VERY WEAK!")
        print("     - Check if microphone is properly connected")
        print("     - Check if microphone is muted in system settings")
        print("     - Try: alsamixer or pavucontrol to check levels")
        print("     - Speak LOUDER or move microphone closer")
    elif suppressed_count > samples_read * 0.5:
        print("  ⚠️  PROBLEM: Noise gate is TOO AGGRESSIVE!")
        print("     - Gate threshold should be lower than your minimum signal")
        print(f"     - Current gate: {config.NOISE_GATE_RMS}")
        print(f"     - Suggestion: Set to {max(config.NOISE_GATE_RMS * 0.3, 0.0001):.6f}")
    elif max_rms > config.TARGET_RMS * 5:
        print("  ⚠️  WARNING: Signal is VERY LOUD!")
        print("     - Microphone input might be too high")
        print("     - Check system volume levels")
    else:
        print("  ✓ Microphone signal looks GOOD")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    diagnose_audio()
