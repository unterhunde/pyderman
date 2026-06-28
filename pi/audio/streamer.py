"""UDP microphone streaming service."""

from __future__ import annotations

import signal
import socket

import numpy as np
import pyaudio

from pi.audio import config
from pi.audio.calibration_telemetry import CalibrationTelemetryServer
from pi.audio.device_selection import select_input_device
from pi.audio.protocol import AUDIO_HEADER
from pi.audio.signal_processing import apply_agc_and_gate_with_metrics, select_mono_channel


class UDPMicStreamer:
    def __init__(
        self,
        host: str,
        port: int,
        sample_rate: int,
        *,
        calibration_bind_host: str,
        calibration_port: int,
    ) -> None:
        self.host = host
        self.port = port
        self.sample_rate = sample_rate
        self.calibration_bind_host = calibration_bind_host
        self.calibration_port = calibration_port
        self.shutdown_requested = False
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Handle SIGTERM and SIGINT gracefully."""
        signal_name = signal.Signals(signum).name
        print(f"Received signal {signal_name}, initiating graceful shutdown")
        self.shutdown_requested = True

    def run(self) -> None:
        audio_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        destination = (self.host, self.port)
        telemetry = CalibrationTelemetryServer(
            bind_host=self.calibration_bind_host,
            port=self.calibration_port,
        )
        telemetry.start()

        pa = pyaudio.PyAudio()
        stream = None
        selected_device_index, selected_device_info = select_input_device(pa, config.INPUT_DEVICE_INDEX)

        max_input_channels = int(selected_device_info.get("maxInputChannels", 0))
        input_channels = min(config.INPUT_CHANNELS, max_input_channels)
        if input_channels <= 0:
            raise RuntimeError(
                f"Input device {selected_device_index} has no input channels: "
                f"{selected_device_info.get('name', 'unknown')}"
            )

        print(
            "Starting mic UDP stream:",
            f"device={selected_device_index} ({selected_device_info.get('name', 'unknown')})",
            f"rate={self.sample_rate}",
            f"input_channels={input_channels}",
            f"output_channels={config.OUTPUT_CHANNELS}",
            f"mode={config.CHANNEL_MODE}",
            f"target_rms={config.TARGET_RMS}",
            f"max_gain={config.MAX_GAIN}",
            f"dest={self.host}:{self.port}",
        )
        stream = pa.open(
            format=config.FORMAT,
            channels=input_channels,
            rate=self.sample_rate,
            input=True,
            input_device_index=selected_device_index,
            frames_per_buffer=config.CHUNK_FRAMES,
        )

        sequence_number = 0
        active_channel = 0
        current_gain = 1.0

        try:
            while True:
                # Check if shutdown was requested
                if self.shutdown_requested:
                    print("Shutdown requested, exiting main loop")
                    break
                
                stereo_pcm = stream.read(config.CHUNK_FRAMES, exception_on_overflow=False)
                samples = np.frombuffer(stereo_pcm, dtype=np.int32)
                if samples.size != config.CHUNK_FRAMES * input_channels:
                    telemetry.record_chunk_drop(1)
                    continue

                mono, active_channel = select_mono_channel(
                    samples=samples,
                    input_channels=input_channels,
                    channel_mode=config.CHANNEL_MODE,
                    active_channel=active_channel,
                )
                pcm_data, current_gain, processing_metrics = apply_agc_and_gate_with_metrics(
                    mono=mono,
                    current_gain=current_gain,
                    noise_gate_rms=config.NOISE_GATE_RMS,
                    target_rms=config.TARGET_RMS,
                    min_gain=config.MIN_GAIN,
                    max_gain=config.MAX_GAIN,
                    agc_attack=config.AGC_ATTACK,
                    agc_release=config.AGC_RELEASE,
                )
                header = AUDIO_HEADER.pack(sequence_number, config.CHUNK_FRAMES)
                audio_sock.sendto(header + pcm_data, destination)
                telemetry.record_chunk(
                    sequence_number=sequence_number,
                    raw_rms=processing_metrics.raw_rms,
                    processed_rms=processing_metrics.processed_rms,
                    peak=processing_metrics.peak,
                    clipping_ratio=processing_metrics.clipping_ratio,
                    gate_active=processing_metrics.gate_active,
                    agc_gain=processing_metrics.agc_gain,
                    active_channel=active_channel,
                )
                sequence_number = (sequence_number + 1) & 0xFFFFFFFF
        except KeyboardInterrupt:
            print("Audio streamer interrupted by user")
        except Exception as exc:
            print(f"Audio streamer error: {exc}")
        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()
            pa.terminate()
            telemetry.stop()
            audio_sock.close()
