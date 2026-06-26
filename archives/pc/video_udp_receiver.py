"""Compatibility façade for the modular video receiver package."""

from __future__ import annotations

try:
    from pc.video.receiver_widget import UDPVideoReceiver, UDPVideoReciever
except ImportError:
    from video.receiver_widget import UDPVideoReceiver, UDPVideoReciever

__all__ = ["UDPVideoReceiver", "UDPVideoReciever"]

