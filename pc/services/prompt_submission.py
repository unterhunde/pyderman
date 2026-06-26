"""Shared prompt submission types for the speech -> LLM pipeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptSubmission:
    phrase_id: int
    text: str

