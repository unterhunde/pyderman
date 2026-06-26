"""UDP wire protocol for video chunk transport."""

from __future__ import annotations

import struct

# Packet types
PACKET_TYPE_CHUNK = 0
PACKET_TYPE_HEARTBEAT = 1

MAX_UDP_PAYLOAD = 1200
CHUNK_HEADER = struct.Struct("!IHH")  # frame_id, total_chunks, chunk_index
HEARTBEAT_PACKET = struct.Struct("!BQ")  # packet_type, timestamp (milliseconds)


