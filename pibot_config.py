"""Centralized runtime configuration for PiBot PC/Pi scripts."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppSettings:
    udp_bind_host: str
    pc_host: str
    udp_audio_port: int
    udp_video_port: int
    whisper_sample_rate: int
    pi_sample_rate: int
    yolo_model_path: str
    ollama_url: str
    ollama_model: str
    pi_host: str
    pi_user: str
    pi_venv_path: str
    pi_project_path: str


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_settings() -> AppSettings:
    project_root = Path(__file__).resolve().parent
    env_file = os.environ.get("PIBOT_CONFIG_FILE", str(project_root / "pibot.env"))
    file_values = _parse_env_file(Path(env_file))

    def get_str(name: str, default: str) -> str:
        return os.environ.get(name, file_values.get(name, default))

    def get_int(name: str, default: int) -> int:
        raw = os.environ.get(name, file_values.get(name))
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError:
            return default

    model_path = Path(get_str("PIBOT_YOLO_MODEL_PATH", "yolo26m.pt"))
    if not model_path.is_absolute():
        model_path = project_root / model_path

    return AppSettings(
        udp_bind_host=get_str("PIBOT_UDP_BIND_HOST", "0.0.0.0"),
        pc_host=get_str("PIBOT_PC_HOST", "192.168.0.189"),
        udp_audio_port=get_int("PIBOT_UDP_AUDIO_PORT", 5001),
        udp_video_port=get_int("PIBOT_UDP_VIDEO_PORT", 5000),
        whisper_sample_rate=get_int("PIBOT_WHISPER_SAMPLE_RATE", 16000),
        pi_sample_rate=get_int("PIBOT_PI_SAMPLE_RATE", 48000),
        yolo_model_path=str(model_path),
        ollama_url=get_str("PIBOT_OLLAMA_URL", "http://localhost:11434/api/generate"),
        ollama_model=get_str("PIBOT_OLLAMA_MODEL", "llama3:instruct"),
        pi_host=get_str("PIBOT_PI_HOST", "192.168.0.38"),
        pi_user=get_str("PIBOT_PI_USER", "jorg"),
        pi_venv_path=get_str("PIBOT_PI_VENV_PATH", "/home/jorg/venv"),
        pi_project_path=get_str("PIBOT_PI_PROJECT_PATH", "/home/jorg/pibot"),
    )
