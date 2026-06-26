"""Startup checks for model files, UDP readiness, and Ollama connectivity."""

from __future__ import annotations

import socket
from pathlib import Path
from urllib.parse import urlparse

import requests


class StartupChecks:
    def __init__(self, settings) -> None:
        self.settings = settings

    def run_all(self, server_url: str, connected: bool) -> tuple[tuple[str, str], tuple[str, str], tuple[str, str]]:
        model_ok, model_text = self.check_model()
        udp_ok, udp_message = self.check_udp_binds(connected)
        target_ok, target_message = self.check_stream_target_alignment()
        udp_ok = udp_ok and target_ok
        udp_text = f"UDP: {udp_message}; target={target_message}"
        ollama_ok, ollama_message = self.check_ollama(server_url)

        return (
            (model_text, "StatusValue.TLabel" if model_ok else "Danger.TLabel"),
            (udp_text, "StatusValue.TLabel" if udp_ok else "Danger.TLabel"),
            (f"Ollama: {ollama_message}", "StatusValue.TLabel" if ollama_ok else "Danger.TLabel"),
        )

    def check_model(self) -> tuple[bool, str]:
        model_path = Path(self.settings.yolo_model_path)
        model_ok = model_path.exists()
        return model_ok, f"Model: {'ok' if model_ok else 'missing'} ({model_path.name})"

    def check_udp_binds(self, connected: bool) -> tuple[bool, str]:
        sockets: list[socket.socket] = []
        try:
            for port in (self.settings.udp_audio_port, self.settings.udp_video_port):
                probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                probe.bind((self.settings.udp_bind_host, port))
                sockets.append(probe)
            return True, "ports available"
        except OSError as exc:
            if connected:
                return True, "bound by running client"
            return False, f"bind failed ({exc})"
        finally:
            for sock in sockets:
                sock.close()

    def check_ollama(self, server_url: str) -> tuple[bool, str]:
        try:
            base = self.ollama_base_url(server_url)
            response = requests.get(f"{base}/api/tags", timeout=3)
            response.raise_for_status()
            return True, "reachable"
        except Exception as exc:
            return False, f"unreachable ({exc})"

    def check_stream_target_alignment(self) -> tuple[bool, str]:
        if self.settings.pc_host in {"127.0.0.1", "localhost", "0.0.0.0"}:
            return True, self.settings.pc_host
        local_ips = {"127.0.0.1"}
        try:
            local_ips.update(socket.gethostbyname_ex(socket.gethostname())[2])
        except OSError:
            pass
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            probe.connect(("8.8.8.8", 80))
            local_ips.add(probe.getsockname()[0])
            probe.close()
        except OSError:
            pass
        if self.settings.pc_host in local_ips:
            return True, self.settings.pc_host
        return False, f"mismatch ({self.settings.pc_host} not in {sorted(local_ips)})"

    def ollama_base_url(self, url: str) -> str:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            fallback = urlparse(self.settings.ollama_url)
            if fallback.scheme and fallback.netloc:
                return f"{fallback.scheme}://{fallback.netloc}"
            return "http://localhost:11434"
        return f"{parsed.scheme}://{parsed.netloc}"

