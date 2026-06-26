"""Compatibility shim for typo'd module name.

Use ``pc.mic_udp_receiver`` instead.
"""

try:
    from mic_udp_receiver import UDPAudioReceiver
except ImportError:
    from pc.mic_udp_receiver import UDPAudioReceiver

__all__ = ["UDPAudioReceiver"]
