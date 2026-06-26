"""Compatibility shim for typo'd module name.

Use ``pc.video_udp_receiver`` instead.
"""

try:
    from video_udp_receiver import UDPVideoReceiver, UDPVideoReciever
except ImportError:
    from pc.video_udp_receiver import UDPVideoReceiver, UDPVideoReciever

__all__ = ["UDPVideoReceiver", "UDPVideoReciever"]
