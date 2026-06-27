"""Tkinter operator console orchestration and UI."""

from __future__ import annotations

import logging
import os
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import scrolledtext, ttk

import numpy as np

from pc.logging_utils import GuiLogHandler
from pc.runtime_config import RuntimeConfig
from pc.services.audio_receiver import AudioReceiverService
from pc.services.ollama_service import OllamaService
from pc.services.pi_streamer_manager import PiStreamerManager
from pc.services.prompt_submission import PromptSubmission
from pc.services.startup_checks import StartupChecks
from pc.services.whisper_service import WhisperService
from pc.video.receiver_widget import UDPVideoReceiver


class OperatorConsoleApp:
    def __init__(self, root: tk.Tk, settings) -> None:
        self.root = root
        self.settings = settings
        self.root.title("PiBot Operator Console")
        self.root.geometry("1500x980")
        self.root.minsize(1280, 840)
        self.root.configure(bg="#141619")

        self.config = RuntimeConfig()
        self.connected = False
        self.stop_event = threading.Event()
        self.audio_queue: queue.Queue[tuple[np.ndarray, float]] = queue.Queue(maxsize=400)
        self.ollama_queue: queue.Queue[PromptSubmission] = queue.Queue(maxsize=16)
        self.log_queue: queue.Queue[str] = queue.Queue(maxsize=2000)
        self.ui_queue: queue.Queue[tuple[object, tuple, dict]] = queue.Queue(maxsize=4000)
        self.last_audio_packet_time = 0.0
        self.last_video_packet_time = 0.0
        self.last_heartbeat_time = 0.0
        self.video_packet_count = 0
        self.video_frame_count = 0
        self._ollama_server_url_lock = threading.Lock()
        self._ollama_server_url = self.settings.ollama_url
        self._streamer_control_lock = threading.Lock()
        self._streamer_action_tokens = {"mic": 0, "video": 0}
        self._streamer_pending_actions: dict[str, str | None] = {"mic": None, "video": None}
        self._streamer_action_worker_running = {"mic": False, "video": False}
        self._streamer_refresh_tokens = {"mic": 0, "video": 0}
        self._streamer_refresh_owner_action_token: dict[str, int | None] = {"mic": None, "video": None}
        self._streamer_refresh_worker_running = {"mic": False, "video": False}

        self.audio_receiver: AudioReceiverService | None = None
        self.whisper_worker: WhisperService | None = None
        self.ollama_worker: OllamaService | None = None
        self.video_widget: UDPVideoReceiver | None = None

        self.startup_checks = StartupChecks(settings=self.settings)
        self.streamer_manager = PiStreamerManager(settings=self.settings)
        self.logger = self._build_logger()
        self._configure_theme()
        self._build_ui()
        self._start_ui_loops()
        self.run_startup_checks()
        self.refresh_streamer_status()
        self.logger.info("Operator console ready")

    def _build_logger(self) -> logging.Logger:
        formatter = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%H:%M:%S")
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)

        gui_handler = GuiLogHandler(self.log_queue)
        gui_handler.setFormatter(formatter)

        logger = logging.getLogger("pibot.console")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        logger.propagate = False
        logger.addHandler(stream_handler)
        logger.addHandler(gui_handler)

        for name in ("pibot.video_receiver",):
            extra_logger = logging.getLogger(name)
            extra_logger.setLevel(logging.INFO)
            extra_logger.handlers.clear()
            extra_logger.propagate = False
            extra_logger.addHandler(stream_handler)
            extra_logger.addHandler(gui_handler)

        return logger

    def _configure_theme(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")

        bg = "#141619"
        panel = "#1d2228"
        panel_alt = "#252c33"
        fg = "#E6EDF3"

        style.configure("App.TFrame", background=bg)
        style.configure("Panel.TFrame", background=panel)
        style.configure("Header.TFrame", background=panel_alt)
        style.configure("TLabel", background=panel, foreground=fg, font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=panel_alt, foreground="#9CDCFE", font=("Segoe UI", 10, "bold"))
        style.configure("Help.TLabel", background=panel, foreground="#8B949E", font=("Segoe UI", 9))
        style.configure("StatusValue.TLabel", background=panel, foreground="#7EE787")
        style.configure("Warn.TLabel", background=panel, foreground="#F2CC60")
        style.configure("Danger.TLabel", background=panel, foreground="#FF7B72")
        style.configure("TLabelframe", background=panel, bordercolor="#30363D", relief="solid")
        style.configure("TLabelframe.Label", background=panel, foreground="#9CDCFE", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", background="#30363D", foreground=fg, padding=(10, 6), font=("Segoe UI", 10))
        style.map("Accent.TButton", background=[("!disabled", "#2F81F7")], foreground=[("!disabled", "#FFFFFF")])
        style.configure("TCheckbutton", background=panel, foreground=fg, indicatorcolor="#0F141A")
        style.configure("TEntry", fieldbackground="#0F141A", foreground=fg)
        style.configure("Horizontal.TScale", background=panel, troughcolor="#0F141A")
        style.configure("Horizontal.TProgressbar", troughcolor="#0F141A", background="#2F81F7", bordercolor="#0F141A")
        style.configure("TNotebook", background=panel, borderwidth=0)
        style.configure("TNotebook.Tab", background="#252c33", foreground=fg, padding=(10, 6))
        style.map("TNotebook.Tab", background=[("selected", "#1d2228")], foreground=[("selected", "#9CDCFE")])

    def _build_ui(self) -> None:
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self._build_connection_bar()
        self._build_main_panels()
        self._build_status_bar()

    def _build_connection_bar(self) -> None:
        bar = ttk.Frame(self.root, style="Header.TFrame", padding=(12, 10))
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_columnconfigure(3, weight=1)
        bar.grid_columnconfigure(8, weight=1)

        ttk.Label(bar, text="Connection Status", style="Header.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.connection_value = ttk.Label(bar, text="Disconnected", style="Danger.TLabel")
        self.connection_value.grid(row=0, column=1, sticky="w")

        ttk.Label(bar, text="Server", style="Header.TLabel").grid(row=0, column=2, sticky="e", padx=(20, 8))
        self.server_var = tk.StringVar(value=self.settings.ollama_url)
        self.server_var.trace_add("write", self._on_server_var_changed)
        self._sync_ollama_server_url_from_var()
        self.server_entry = ttk.Entry(bar, textvariable=self.server_var, width=44)
        self.server_entry.grid(row=0, column=3, sticky="ew", padx=(0, 12))

        self.connect_btn = ttk.Button(bar, text="Connect", style="Accent.TButton", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=4, sticky="e")
        ttk.Label(
            bar,
            text="Workflow: Connect -> verify startup checks -> start listening/inference.",
            style="Help.TLabel",
        ).grid(row=0, column=5, sticky="w", padx=(16, 0))

        ttk.Label(bar, text="Startup Checks", style="Header.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.check_model_value = ttk.Label(bar, text="Model: pending", style="Warn.TLabel")
        self.check_model_value.grid(row=1, column=1, sticky="w", pady=(8, 0))
        self.check_udp_value = ttk.Label(bar, text="UDP: pending", style="Warn.TLabel")
        self.check_udp_value.grid(row=1, column=2, sticky="w", pady=(8, 0))
        self.check_ollama_value = ttk.Label(bar, text="Ollama: pending", style="Warn.TLabel")
        self.check_ollama_value.grid(row=1, column=3, sticky="w", pady=(8, 0))
        self.check_button = ttk.Button(bar, text="Run Checks", command=self.run_startup_checks)
        self.check_button.grid(row=1, column=4, sticky="e", pady=(8, 0))

    def _on_server_var_changed(self, *_args: object) -> None:
        self._sync_ollama_server_url_from_var()

    def _sync_ollama_server_url_from_var(self) -> None:
        server_url = self.server_var.get().strip() or self.settings.ollama_url
        with self._ollama_server_url_lock:
            self._ollama_server_url = server_url

    def _get_ollama_server_url(self) -> str:
        with self._ollama_server_url_lock:
            return self._ollama_server_url

    def _build_main_panels(self) -> None:
        content = ttk.Frame(self.root, style="App.TFrame", padding=(12, 10))
        content.grid(row=2, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=9)
        content.grid_rowconfigure(0, weight=1)

        self.left_panel = ttk.Frame(content, style="Panel.TFrame", padding=12)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.left_panel.grid_columnconfigure(0, weight=1)
        self.left_panel.grid_rowconfigure(0, weight=1)

        self.center_panel = ttk.Frame(content, style="Panel.TFrame", padding=12)
        self.center_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.center_panel.grid_columnconfigure(0, weight=1)
        self.center_panel.grid_rowconfigure(2, weight=1)

        self._build_left_panel()
        self._build_center_panel()

    def _build_left_panel(self) -> None:
        notebook = ttk.Notebook(self.left_panel)
        notebook.grid(row=0, column=0, sticky="nsew")

        whisper_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=10)
        inference_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=10)
        streamers_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=10)
        audio_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=10)
        logs_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=10)

        notebook.add(whisper_tab, text="Whisper")
        notebook.add(inference_tab, text="Inference")
        notebook.add(streamers_tab, text="Streamers")
        notebook.add(audio_tab, text="Audio")
        notebook.add(logs_tab, text="Logs")

        self._build_whisper_tab(whisper_tab)
        self._build_inference_tab(inference_tab)
        self._build_streamers_tab(streamers_tab)
        self._build_audio_tab(audio_tab)
        self._build_logs_tab(logs_tab)

    def _build_whisper_tab(self, whisper: ttk.Frame) -> None:
        whisper.grid_columnconfigure(0, weight=1)
        whisper.grid_rowconfigure(7, weight=1)

        whisper_header = ttk.LabelFrame(whisper, text="Whisper Controls", padding=10)
        whisper_header.grid(row=0, column=0, sticky="nsew")
        whisper_header.grid_columnconfigure(0, weight=1)
        whisper_header.grid_columnconfigure(1, weight=1)
        whisper_header.grid_rowconfigure(7, weight=1)

        whisper.grid_columnconfigure(0, weight=1)
        whisper.grid_columnconfigure(1, weight=1)
        ttk.Label(
            whisper_header,
            text="Speech capture and transcription. Use Start/Stop Listening to control phrase detection.",
            style="Help.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Button(whisper_header, text="Start Listening", command=self.start_listening).grid(row=1, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(whisper_header, text="Stop Listening", command=self.stop_listening).grid(row=1, column=1, sticky="ew")

        ttk.Label(whisper_header, text="Mic Status").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.mic_status_value = ttk.Label(whisper_header, text="Idle", style="Warn.TLabel")
        self.mic_status_value.grid(row=2, column=1, sticky="e", pady=(8, 0))

        ttk.Label(whisper_header, text="Transcript Status").grid(row=3, column=0, sticky="w")
        self.transcript_status_value = ttk.Label(whisper_header, text="Idle", style="Warn.TLabel")
        self.transcript_status_value.grid(row=3, column=1, sticky="e")

        ttk.Label(whisper_header, text="Partial Transcript").grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.partial_transcript_var = tk.StringVar(value="")
        self.partial_transcript_label = ttk.Label(whisper_header, textvariable=self.partial_transcript_var, wraplength=320, justify="left")
        self.partial_transcript_label.grid(row=5, column=0, columnspan=2, sticky="ew")

        ttk.Label(whisper_header, text="Final Transcript").grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.final_transcript_box = scrolledtext.ScrolledText(
            whisper_header,
            height=4,
            wrap=tk.WORD,
            bg="#0F141A",
            fg="#E6EDF3",
            insertbackground="#E6EDF3",
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            font=("Consolas", 10),
        )
        self.final_transcript_box.grid(row=7, column=0, columnspan=2, sticky="nsew", pady=(4, 0))

        assistant = ttk.LabelFrame(whisper_header, text="Assistant Output", padding=8)
        assistant.grid(row=8, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        assistant.grid_columnconfigure(0, weight=1)
        assistant.grid_rowconfigure(0, weight=1)
        whisper_header.grid_rowconfigure(8, weight=1)

        self.ai_output_box = scrolledtext.ScrolledText(
            assistant,
            height=7,
            wrap=tk.WORD,
            bg="#0F141A",
            fg="#E6EDF3",
            insertbackground="#E6EDF3",
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            font=("Consolas", 10),
        )
        self.ai_output_box.grid(row=0, column=0, sticky="nsew")

    def _build_audio_tab(self, audio_tab: ttk.Frame) -> None:
        audio_tab.grid_columnconfigure(0, weight=1)
        audio = ttk.LabelFrame(audio_tab, text="Audio Streaming Controls", padding=10)
        audio.grid(row=0, column=0, sticky="nsew")
        audio.grid_columnconfigure(1, weight=1)
        ttk.Label(
            audio,
            text="Controls UDP audio ingest into Whisper. Disable stream to pause incoming audio buffering.",
            style="Help.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        self.audio_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(audio, text="Enable Audio Stream", variable=self.audio_enabled_var, command=self.toggle_audio_stream).grid(
            row=1, column=0, columnspan=2, sticky="w"
        )

        ttk.Label(audio, text="Audio Level").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.audio_meter = ttk.Progressbar(audio, orient="horizontal", mode="determinate", maximum=0.20)
        self.audio_meter.grid(row=2, column=1, sticky="ew", pady=(8, 0))
        self.audio_level_label = ttk.Label(audio, text="RMS: 0.0000")
        self.audio_level_label.grid(row=3, column=1, sticky="e")

        ttk.Label(audio, text="Stream Status").grid(row=4, column=0, sticky="w", pady=(6, 0))
        self.audio_stream_status = ttk.Label(audio, text="Disabled", style="Warn.TLabel")
        self.audio_stream_status.grid(row=4, column=1, sticky="e", pady=(6, 0))

        ttk.Label(audio, text="Volume Threshold").grid(row=5, column=0, sticky="w", pady=(8, 0))
        self.threshold_var = tk.DoubleVar(value=self.config.get_threshold())
        ttk.Scale(audio, from_=0.001, to=0.20, variable=self.threshold_var, command=self._on_threshold_change).grid(
            row=5, column=1, sticky="ew", pady=(8, 0)
        )

        ttk.Label(audio, text="Silence Timeout (s)").grid(row=6, column=0, sticky="w", pady=(8, 0))
        self.silence_var = tk.DoubleVar(value=self.config.get_silence_timeout())
        ttk.Scale(audio, from_=0.5, to=3.0, variable=self.silence_var, command=self._on_silence_change).grid(
            row=6, column=1, sticky="ew", pady=(8, 0)
        )

    def _build_logs_tab(self, logs_tab: ttk.Frame) -> None:
        logs_tab.grid_columnconfigure(0, weight=1)
        logs_tab.grid_rowconfigure(0, weight=1)
        self.log_box = scrolledtext.ScrolledText(
            logs_tab,
            wrap=tk.WORD,
            bg="#0B1016",
            fg="#C9D1D9",
            insertbackground="#C9D1D9",
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            font=("Consolas", 9),
        )
        self.log_box.grid(row=0, column=0, sticky="nsew")

    def _build_center_panel(self) -> None:
        ttk.Label(self.center_panel, text="Live Video Preview + Inference Overlay", style="Header.TLabel").grid(
            row=0, column=0, sticky="w"
        )

        video_status = ttk.Frame(self.center_panel, style="Panel.TFrame")
        video_status.grid(row=1, column=0, sticky="ew")
        video_status.grid_columnconfigure(1, weight=1)
        video_status.grid_columnconfigure(3, weight=1)
        ttk.Label(video_status, text="Video Stream").grid(row=0, column=0, sticky="w")
        self.video_stream_value = ttk.Label(video_status, text="Waiting for packets", style="Warn.TLabel")
        self.video_stream_value.grid(row=0, column=1, sticky="w")
        ttk.Label(video_status, text="Packets/Frames").grid(row=0, column=2, sticky="w")
        self.video_counts_value = ttk.Label(video_status, text="0 / 0", style="Warn.TLabel")
        self.video_counts_value.grid(row=0, column=3, sticky="w")

        self.video_container = ttk.Frame(self.center_panel, style="Panel.TFrame")
        self.video_container.grid(row=2, column=0, sticky="nsew", pady=(8, 8))
        self.video_container.grid_rowconfigure(0, weight=1)
        self.video_container.grid_columnconfigure(0, weight=1)

        self.video_placeholder = tk.Label(
            self.video_container,
            text="Video stream idle",
            anchor="center",
            justify="center",
            bg="#000000",
            fg="#D0D7DE",
        )
        self.video_placeholder.grid(row=0, column=0, sticky="nsew")

        stats = ttk.Frame(self.center_panel, style="Panel.TFrame")
        stats.grid(row=3, column=0, sticky="ew")
        stats.grid_columnconfigure(1, weight=1)
        stats.grid_columnconfigure(3, weight=1)

        ttk.Label(stats, text="FPS").grid(row=0, column=0, sticky="w")
        self.fps_value = ttk.Label(stats, text="0.0", style="StatusValue.TLabel")
        self.fps_value.grid(row=0, column=1, sticky="w")
        ttk.Label(stats, text="Frame Statistics").grid(row=0, column=2, sticky="w")
        self.frame_stats_value = ttk.Label(stats, text="frame=0 | infer=0.0ms", style="StatusValue.TLabel")
        self.frame_stats_value.grid(row=0, column=3, sticky="w")

    def _build_inference_tab(self, inference_tab: ttk.Frame) -> None:
        inference_tab.grid_columnconfigure(0, weight=1)
        inference = ttk.LabelFrame(inference_tab, text="Inference Controls", padding=10)
        inference.grid(row=0, column=0, sticky="nsew")
        inference.grid_columnconfigure(0, weight=1)
        inference.grid_columnconfigure(1, weight=1)
        ttk.Label(
            inference,
            text="Run object detection overlay on incoming video frames.",
            style="Help.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Button(inference, text="Start Inference", command=self.start_inference).grid(row=1, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(inference, text="Stop Inference", command=self.stop_inference).grid(row=1, column=1, sticky="ew")
        ttk.Label(inference, text="Model Status").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.model_status_value = ttk.Label(inference, text="Idle", style="Warn.TLabel")
        self.model_status_value.grid(row=2, column=1, sticky="e", pady=(8, 0))
        ttk.Label(inference, text="Detection Statistics").grid(row=3, column=0, sticky="w")
        self.detection_stats_value = ttk.Label(inference, text="0 detections", style="StatusValue.TLabel")
        self.detection_stats_value.grid(row=3, column=1, sticky="e")

    def _build_streamers_tab(self, streamers_tab: ttk.Frame) -> None:
        streamers_tab.grid_columnconfigure(0, weight=1)
        streamers = ttk.LabelFrame(streamers_tab, text="Streamer Controls", padding=10)
        streamers.grid(row=0, column=0, sticky="nsew")
        streamers.grid_columnconfigure(0, weight=1)
        streamers.grid_columnconfigure(1, weight=1)
        ttk.Label(
            streamers,
            text="Start/stop Pi-side UDP streamer scripts over SSH.",
            style="Help.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Button(streamers, text="Start Mic Streamer", command=self.start_mic_streamer).grid(
            row=1, column=0, sticky="ew", padx=(0, 6)
        )
        ttk.Button(streamers, text="Stop Mic Streamer", command=self.stop_mic_streamer).grid(row=1, column=1, sticky="ew")
        ttk.Label(streamers, text="Mic Streamer").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.mic_streamer_status = ttk.Label(streamers, text="Unknown", style="Warn.TLabel")
        self.mic_streamer_status.grid(row=2, column=1, sticky="e", pady=(6, 0))

        ttk.Button(streamers, text="Start Video Streamer", command=self.start_video_streamer).grid(
            row=3, column=0, sticky="ew", padx=(0, 6), pady=(8, 0)
        )
        ttk.Button(streamers, text="Stop Video Streamer", command=self.stop_video_streamer).grid(
            row=3, column=1, sticky="ew", pady=(8, 0)
        )
        ttk.Label(streamers, text="Video Streamer").grid(row=4, column=0, sticky="w", pady=(6, 0))
        self.video_streamer_status = ttk.Label(streamers, text="Unknown", style="Warn.TLabel")
        self.video_streamer_status.grid(row=4, column=1, sticky="e", pady=(6, 0))
        ttk.Button(streamers, text="Refresh Streamer Status", command=self.refresh_streamer_status).grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0)
        )

    def _build_bottom_panel(self) -> None:
        bottom = ttk.LabelFrame(self.root, text="Log Console", padding=10)
        bottom.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 10))
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_rowconfigure(0, weight=1)
        self.log_box = scrolledtext.ScrolledText(
            bottom,
            height=10,
            wrap=tk.WORD,
            bg="#0B1016",
            fg="#C9D1D9",
            insertbackground="#C9D1D9",
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            font=("Consolas", 9),
        )
        self.log_box.grid(row=0, column=0, sticky="nsew")

    def _build_status_bar(self) -> None:
        status = ttk.Frame(self.root, style="Header.TFrame", padding=(12, 6))
        status.grid(row=3, column=0, sticky="ew")
        for i in range(10):
            status.grid_columnconfigure(i, weight=1)

        ttk.Label(status, text="CPU", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        self.cpu_value = ttk.Label(status, text="0%", style="StatusValue.TLabel")
        self.cpu_value.grid(row=0, column=1, sticky="w")
        ttk.Label(status, text="Memory", style="Header.TLabel").grid(row=0, column=2, sticky="w")
        self.memory_value = ttk.Label(status, text="0 MB", style="StatusValue.TLabel")
        self.memory_value.grid(row=0, column=3, sticky="w")
        ttk.Label(status, text="Audio", style="Header.TLabel").grid(row=0, column=4, sticky="w")
        self.audio_state_value = ttk.Label(status, text="idle", style="Warn.TLabel")
        self.audio_state_value.grid(row=0, column=5, sticky="w")
        ttk.Label(status, text="Video", style="Header.TLabel").grid(row=0, column=6, sticky="w")
        self.video_state_value = ttk.Label(status, text="idle", style="Warn.TLabel")
        self.video_state_value.grid(row=0, column=7, sticky="w")
        ttk.Label(status, text="Network", style="Header.TLabel").grid(row=0, column=8, sticky="w")
        self.network_state_value = ttk.Label(status, text="offline", style="Danger.TLabel")
        self.network_state_value.grid(row=0, column=9, sticky="w")

    def _start_ui_loops(self) -> None:
        self._drain_ui_queue()
        self._drain_log_queue()
        self._refresh_status_bar()

    def _post_ui(self, callback, *args, **kwargs) -> None:
        try:
            self.ui_queue.put_nowait((callback, args, kwargs))
        except queue.Full:
            self.logger.warning("UI queue full; dropping UI update")

    def _drain_ui_queue(self) -> None:
        processed = 0
        while processed < 200:
            try:
                callback, args, kwargs = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            callback(*args, **kwargs)
            processed += 1
        self.root.after(20, self._drain_ui_queue)

    def _drain_log_queue(self) -> None:
        if not hasattr(self, 'log_box'):
            self.root.after(80, self._drain_log_queue)
            return
        wrote = False
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_box.insert(tk.END, line + "\n")
            wrote = True
        if wrote:
            self.log_box.see(tk.END)
        self.root.after(80, self._drain_log_queue)

    def _refresh_status_bar(self) -> None:
        self.cpu_value.configure(text=f"{self._read_cpu_percent():.1f}%")
        self.memory_value.configure(text=f"{self._read_memory_mb():.1f} MB")
        now = time.monotonic()
        audio_recent = (now - self.last_audio_packet_time) < 2.0
        video_recent = (now - self.last_video_packet_time) < 2.0
        heartbeat_recent = (now - self.last_heartbeat_time) < 2.0
        
        # Network is online if we have heartbeat, or both audio and video (for backward compat)
        network_live = self.connected and (heartbeat_recent or (audio_recent and video_recent))
        
        self.audio_state_value.configure(text="active" if audio_recent else "idle")
        self.video_state_value.configure(text="active" if video_recent else "idle")
        self.network_state_value.configure(text="online" if network_live else "offline")
        self.root.after(1000, self._refresh_status_bar)

    def _read_cpu_percent(self) -> float:
        try:
            return max(0.0, min(100.0, (os.getloadavg()[0] / max(1, os.cpu_count() or 1)) * 100.0))
        except OSError:
            return 0.0

    def _read_memory_mb(self) -> float:
        try:
            with open("/proc/self/status", "r", encoding="utf-8") as status_file:
                for line in status_file:
                    if line.startswith("VmRSS:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            return float(parts[1]) / 1024.0
        except OSError:
            pass
        return 0.0

    def run_startup_checks(self) -> None:
        self.check_model_value.configure(text="Model: checking...", style="Warn.TLabel")
        self.check_udp_value.configure(text="UDP: checking...", style="Warn.TLabel")
        self.check_ollama_value.configure(text="Ollama: checking...", style="Warn.TLabel")
        self.check_button.state(["disabled"])
        self._sync_ollama_server_url_from_var()
        server_url = self._get_ollama_server_url()
        threading.Thread(target=self._startup_checks_worker, args=(server_url,), daemon=True).start()

    def _startup_checks_worker(self, server_url: str) -> None:
        model, udp, ollama = self.startup_checks.run_all(server_url=server_url, connected=self.connected)
        self._post_ui(self._update_check_results, model, udp, ollama)

    def _update_check_results(
        self,
        model: tuple[str, str],
        udp: tuple[str, str],
        ollama: tuple[str, str],
    ) -> None:
        self.check_model_value.configure(text=model[0], style=model[1])
        self.check_udp_value.configure(text=udp[0], style=udp[1])
        self.check_ollama_value.configure(text=ollama[0], style=ollama[1])
        self.check_button.state(["!disabled"])
        self.logger.info("%s | %s | %s", model[0], udp[0], ollama[0])

    def toggle_connection(self) -> None:
        if self.connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self) -> None:
        if self.connected:
            return
        try:
            self.logger.info("Starting connection sequence...")
            self._sync_ollama_server_url_from_var()
            self.stop_event = threading.Event()
            self.audio_queue = queue.Queue(maxsize=400)
            self.ollama_queue = queue.Queue(maxsize=16)
            self.last_audio_packet_time = 0.0
            self.last_video_packet_time = 0.0
            self.video_packet_count = 0
            self.video_frame_count = 0

            self.logger.info("Creating AudioReceiverService...")
            self.audio_receiver = AudioReceiverService(
                self.audio_queue,
                self.stop_event,
                self.config,
                self.update_audio_meter,
                self._mark_audio_packet,
                self.logger,
                self.settings.udp_bind_host,
                self.settings.udp_audio_port,
            )
            self.logger.info("Creating WhisperService...")
            self.whisper_worker = WhisperService(
                self.audio_queue,
                self.ollama_queue,
                self.config,
                self.stop_event,
                self.set_partial_transcript,
                self.append_final_transcript,
                self.set_transcript_status,
                self.logger,
                sample_rate=self.settings.whisper_sample_rate,
            )
            self.logger.info("Creating OllamaService...")
            self.ollama_worker = OllamaService(
                self.ollama_queue,
                self.stop_event,
                self.reset_ai_output,
                self.append_ai_output,
                self.set_transcript_status,
                self._get_ollama_server_url,
                self.logger,
                model_name=self.settings.ollama_model,
            )

            self.logger.info("Starting audio receiver...")
            self.audio_receiver.start()
            self.logger.info("Starting whisper worker...")
            self.whisper_worker.start()
            self.logger.info("Starting ollama worker...")
            self.ollama_worker.start()
            self.logger.info("Starting video receiver...")
            self._start_video_receiver()

            self.connected = True
            self.connection_value.configure(text="Connected", style="StatusValue.TLabel")
            self.connect_btn.configure(text="Disconnect")
            self.audio_stream_status.configure(text="Enabled", style="StatusValue.TLabel")
            self.model_status_value.configure(text="Inference enabled", style="StatusValue.TLabel")
            self.logger.info("Connected: workers running")
            self.run_startup_checks()
        except Exception as e:
            self.logger.error(f"Connection failed: {e}", exc_info=True)
            self.connection_value.configure(text=f"Error: {str(e)[:50]}", style="Danger.TLabel")
            self.connect_btn.configure(text="Retry Connect")

    def disconnect(self) -> None:
        if not self.connected:
            return
        self.stop_event.set()
        if self.audio_receiver is not None:
            self.audio_receiver.close_socket()
        self._stop_video_receiver()

        self.connected = False
        self.connection_value.configure(text="Disconnected", style="Danger.TLabel")
        self.connect_btn.configure(text="Connect")
        self.mic_status_value.configure(text="Idle", style="Warn.TLabel")
        self.transcript_status_value.configure(text="Idle", style="Warn.TLabel")
        self.audio_stream_status.configure(text="Disabled", style="Warn.TLabel")
        self.model_status_value.configure(text="Idle", style="Warn.TLabel")
        self.logger.info("Disconnected")
        self.run_startup_checks()

    def _start_video_receiver(self) -> None:
        self.video_placeholder.grid_remove()
        self.video_widget = UDPVideoReceiver(
            self.video_container,
            host=self.settings.udp_bind_host,
            port=self.settings.udp_video_port,
            poll_interval_ms=15,
            model_path=self.settings.yolo_model_path,
            inference_enabled=True,
            status_callback=self._on_video_status,
            stats_callback=self._on_video_stats,
            packet_callback=self._on_video_packet,
        )
        self.video_widget.grid(row=0, column=0, sticky="nsew")
        self.video_widget.start()
        self.video_stream_value.configure(text="Listening for packets", style="Warn.TLabel")
        self.video_counts_value.configure(text="0 / 0", style="Warn.TLabel")

    def _stop_video_receiver(self) -> None:
        if self.video_widget is not None:
            self.video_widget.destroy()
            self.video_widget = None
        self.video_placeholder.grid()
        self.video_stream_value.configure(text="Video receiver idle", style="Warn.TLabel")

    def _mark_audio_packet(self) -> None:
        self.last_audio_packet_time = time.monotonic()
        self._post_ui(self.mic_status_value.configure, text="Receiving", style="StatusValue.TLabel")

    def _on_video_status(self, message: str) -> None:
        self.logger.info(message)
        style = "StatusValue.TLabel"
        lower = message.lower()
        if "error" in lower or "stopped" in lower or "waiting" in lower:
            style = "Warn.TLabel"
        self.video_stream_value.configure(text=message, style=style)
        if "Model ready" in message:
            self.model_status_value.configure(text="Model loaded", style="StatusValue.TLabel")

    def _on_video_packet(self) -> None:
        self.video_packet_count += 1
        if self.video_packet_count % 30 == 0:
            self.video_counts_value.configure(text=f"{self.video_packet_count} / {self.video_frame_count}", style="StatusValue.TLabel")
            self.video_stream_value.configure(text="Receiving UDP video packets", style="StatusValue.TLabel")
            self.logger.info(
                "Video packet flow | packets=%s frames=%s",
                self.video_packet_count,
                self.video_frame_count,
            )

    def _on_video_stats(self, stats: dict) -> None:
        self.last_video_packet_time = time.monotonic()
        self.video_frame_count = int(stats["frame_id"]) + 1
        self.fps_value.configure(text=f"{stats['fps']:.1f}")
        self.frame_stats_value.configure(text=f"frame={stats['frame_id']} | infer={stats['inference_ms']:.1f}ms")
        self.detection_stats_value.configure(text=f"{stats['detection_count']} detections")
        self.video_counts_value.configure(text=f"{self.video_packet_count} / {self.video_frame_count}", style="StatusValue.TLabel")
        if self.video_frame_count % 20 == 0:
            self.logger.info(
                "Preview refresh | frame=%s fps=%.2f infer_ms=%.1f detections=%s",
                stats["frame_id"],
                float(stats["fps"]),
                float(stats["inference_ms"]),
                int(stats["detection_count"]),
            )

    def update_audio_meter(self, rms: float) -> None:
        def _update_meter() -> None:
            self.audio_meter.configure(value=min(rms, 0.20))
            self.audio_level_label.configure(text=f"RMS: {rms:.4f}")

        self._post_ui(_update_meter)

    def set_partial_transcript(self, text: str) -> None:
        self._post_ui(self.partial_transcript_var.set, text)

    def append_final_transcript(self, text: str) -> None:
        def _append_transcript() -> None:
            self.final_transcript_box.insert(tk.END, f"{time.strftime('%H:%M:%S')}  {text}\n")
            self.final_transcript_box.see(tk.END)
            self.logger.info("GUI final transcript updated")

        self._post_ui(_append_transcript)

    def set_transcript_status(self, status: str) -> None:
        def _update_status() -> None:
            style = "StatusValue.TLabel" if "Listening" in status else "Warn.TLabel"
            self.transcript_status_value.configure(text=status, style=style)

        self._post_ui(_update_status)

    def reset_ai_output(self) -> None:
        self._post_ui(self.ai_output_box.delete, "1.0", tk.END)

    def append_ai_output(self, text: str) -> None:
        def _append_ai() -> None:
            self.ai_output_box.insert(tk.END, text)
            self.ai_output_box.see(tk.END)

        self._post_ui(_append_ai)

    def toggle_audio_stream(self) -> None:
        enabled = self.audio_enabled_var.get()
        self.config.set_audio_enabled(enabled)
        state = "Enabled" if enabled else "Disabled"
        style = "StatusValue.TLabel" if enabled else "Warn.TLabel"
        self.audio_stream_status.configure(text=state, style=style)
        self.logger.info("Audio stream %s", state.lower())

    def start_listening(self) -> None:
        self.config.set_listening_enabled(True)
        self.logger.info("Listening enabled")
        self.set_transcript_status("Listening")

    def stop_listening(self) -> None:
        self.config.set_listening_enabled(False)
        self.logger.info("Listening paused")
        self.set_transcript_status("Listening paused")

    def start_inference(self) -> None:
        if self.video_widget is not None:
            self.video_widget.set_inference_enabled(True)
            self.model_status_value.configure(text="Inference enabled", style="StatusValue.TLabel")
            self.logger.info("Inference enabled")

    def stop_inference(self) -> None:
        if self.video_widget is not None:
            self.video_widget.set_inference_enabled(False)
            self.model_status_value.configure(text="Inference disabled", style="Warn.TLabel")
            self.logger.info("Inference disabled")

    def start_mic_streamer(self) -> None:
        self._run_streamer_action("mic", "start")

    def stop_mic_streamer(self) -> None:
        self._run_streamer_action("mic", "stop")

    def start_video_streamer(self) -> None:
        self._run_streamer_action("video", "start")

    def stop_video_streamer(self) -> None:
        self._run_streamer_action("video", "stop")

    def refresh_streamer_status(self, streamer: str | None = None) -> None:
        """Refresh streamer status. If streamer specified, only query that one."""
        if streamer is None:
            self._request_streamer_refresh("mic")
            self._request_streamer_refresh("video")
            return
        self._request_streamer_refresh(streamer)

    def _run_streamer_action(self, streamer: str, action: str) -> None:
        with self._streamer_control_lock:
            next_token = self._streamer_action_tokens[streamer] + 1
            self._streamer_action_tokens[streamer] = next_token
            self._streamer_pending_actions[streamer] = action
            worker_running = self._streamer_action_worker_running[streamer]
            if not worker_running:
                self._streamer_action_worker_running[streamer] = True
        self._post_streamer_action_status(
            streamer,
            token=next_token,
            text=f"{action.title()}ing...",
            style="Warn.TLabel",
        )
        self.logger.info("User clicked %s streamer %s button (token=%s)", streamer, action, next_token)
        if not worker_running:
            threading.Thread(target=self._streamer_action_worker, args=(streamer,), daemon=True).start()

    def _streamer_action_worker(self, streamer: str) -> None:
        while True:
            with self._streamer_control_lock:
                action = self._streamer_pending_actions[streamer]
                action_token = self._streamer_action_tokens[streamer]
                self._streamer_pending_actions[streamer] = None
            if action is None:
                with self._streamer_control_lock:
                    self._streamer_action_worker_running[streamer] = False
                    if self._streamer_pending_actions[streamer] is not None:
                        self._streamer_action_worker_running[streamer] = True
                        continue
                return

            self.logger.info("Executing %s on %s streamer (token=%s)...", action, streamer, action_token)
            ok, output = self.streamer_manager.run_action(streamer=streamer, action=action)
            self.logger.info("%s streamer %s result (token=%s): ok=%s, output=%s", streamer, action, action_token, ok, output)

            with self._streamer_control_lock:
                is_latest = action_token == self._streamer_action_tokens[streamer]
            if not is_latest:
                self.logger.info(
                    "Discarding stale %s %s result (token=%s, latest=%s)",
                    streamer,
                    action,
                    action_token,
                    self._streamer_action_tokens[streamer],
                )
                continue

            if not ok:
                self.logger.warning(
                    "%s streamer %s failed (token=%s): %s. Confirming actual Pi state.",
                    streamer,
                    action,
                    action_token,
                    output or "unknown error",
                )

            # Always confirm real Pi state after an action result.
            self._request_streamer_refresh(streamer, owner_action_token=action_token)

    def _request_streamer_refresh(self, streamer: str, owner_action_token: int | None = None) -> None:
        with self._streamer_control_lock:
            next_refresh_token = self._streamer_refresh_tokens[streamer] + 1
            self._streamer_refresh_tokens[streamer] = next_refresh_token
            if owner_action_token is None:
                owner_action_token = self._streamer_action_tokens[streamer]
            self._streamer_refresh_owner_action_token[streamer] = owner_action_token
            refresh_worker_running = self._streamer_refresh_worker_running[streamer]
            if not refresh_worker_running:
                self._streamer_refresh_worker_running[streamer] = True
        self._post_streamer_refresh_status(
            streamer,
            refresh_token=next_refresh_token,
            owner_action_token=owner_action_token,
            text="Checking...",
            style="Warn.TLabel",
        )
        self.logger.info(
            "Queued %s streamer status refresh (refresh_token=%s, owner_action_token=%s)",
            streamer,
            next_refresh_token,
            owner_action_token,
        )
        if not refresh_worker_running:
            threading.Thread(target=self._refresh_streamer_status_worker, args=(streamer,), daemon=True).start()

    def _refresh_streamer_status_worker(self, streamer: str) -> None:
        while True:
            with self._streamer_control_lock:
                refresh_token = self._streamer_refresh_tokens[streamer]
                owner_action_token = self._streamer_refresh_owner_action_token[streamer]

            ok, text = self.streamer_manager.query_status(streamer)
            style = "StatusValue.TLabel" if ok else "Warn.TLabel"
            self._post_streamer_refresh_status(
                streamer,
                refresh_token=refresh_token,
                owner_action_token=owner_action_token,
                text=text,
                style=style,
            )

            self.logger.info(
                "Streamer status | %s=%s | refresh_token=%s | owner_action_token=%s",
                streamer,
                text,
                refresh_token,
                owner_action_token,
            )

            with self._streamer_control_lock:
                latest_refresh_token = self._streamer_refresh_tokens[streamer]
                if refresh_token == latest_refresh_token:
                    self._streamer_refresh_worker_running[streamer] = False
                    if latest_refresh_token == self._streamer_refresh_tokens[streamer]:
                        return
                    self._streamer_refresh_worker_running[streamer] = True

    def _get_streamer_status_widget(self, streamer: str) -> ttk.Label:
        return self.mic_streamer_status if streamer == "mic" else self.video_streamer_status

    def _post_streamer_action_status(self, streamer: str, token: int, text: str, style: str) -> None:
        def _apply_if_current() -> None:
            with self._streamer_control_lock:
                if token != self._streamer_action_tokens[streamer]:
                    return
            self._get_streamer_status_widget(streamer).configure(text=text, style=style)

        self._post_ui(_apply_if_current)

    def _post_streamer_refresh_status(
        self,
        streamer: str,
        refresh_token: int,
        owner_action_token: int | None,
        text: str,
        style: str,
    ) -> None:
        def _apply_if_current() -> None:
            with self._streamer_control_lock:
                latest_refresh_token = self._streamer_refresh_tokens[streamer]
                latest_action_token = self._streamer_action_tokens[streamer]
                latest_owner_action_token = self._streamer_refresh_owner_action_token[streamer]
                if refresh_token != latest_refresh_token:
                    return
                if owner_action_token != latest_owner_action_token:
                    return
                if owner_action_token != latest_action_token:
                    return
            self._get_streamer_status_widget(streamer).configure(text=text, style=style)

        self._post_ui(_apply_if_current)

    def _on_threshold_change(self, _value: str) -> None:
        self.config.set_threshold(float(self.threshold_var.get()))

    def _on_silence_change(self, _value: str) -> None:
        self.config.set_silence_timeout(float(self.silence_var.get()))

    def on_close(self) -> None:
        self.disconnect()
        self.root.destroy()
