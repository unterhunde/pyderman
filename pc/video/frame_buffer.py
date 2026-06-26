"""Chunk assembly primitives for incoming video frames."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FrameBuffer:
    total_chunks: int
    chunks: dict[int, bytes] = field(default_factory=dict)

    def add_chunk(self, chunk_index: int, payload: bytes) -> None:
        if chunk_index not in self.chunks:
            self.chunks[chunk_index] = payload

    def is_complete(self) -> bool:
        return len(self.chunks) == self.total_chunks

    def assemble(self) -> bytes:
        missing_chunks = [i for i in range(self.total_chunks) if i not in self.chunks]
        if missing_chunks:
            raise ValueError(f"Frame buffer incomplete: missing chunks {missing_chunks} of {self.total_chunks}")
        return b"".join(self.chunks[index] for index in range(self.total_chunks))

