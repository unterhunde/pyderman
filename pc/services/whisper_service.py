"""Speech segmentation + Whisper transcription worker."""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections import deque

import numpy as np
import whisper

from pc.services.prompt_submission import PromptSubmission


class WhisperService(threading.Thread):
    def __init__(
        self,
        audio_queue: queue.Queue[tuple[np.ndarray, float]],
        ollama_queue: queue.Queue[PromptSubmission],
        config,
        stop_event: threading.Event,
        on_partial,
        on_final,
        on_status,
        logger: logging.Logger,
        sample_rate: int,
    ) -> None:
        super().__init__(daemon=True)
        self.audio_queue = audio_queue
        self.ollama_queue = ollama_queue
        self.config = config
        self.stop_event = stop_event
        self.on_partial = on_partial
        self.on_final = on_final
        self.on_status = on_status
        self.logger = logger
        self.sample_rate = sample_rate
        self.model = None

    def _get_model(self):
        if self.model is None:
            self.logger.info("Loading Whisper model: base")
            self.model = whisper.load_model("base")
            self.logger.info("Whisper model ready")
        return self.model

    def run(self) -> None:
        pre_roll_chunks: deque[np.ndarray] = deque(maxlen=8)
        phrase_chunks: list[np.ndarray] = []
        speech_active = False
        above_threshold_streak = 0
        voiced_chunk_count = 0
        voiced_seconds = 0.0
        silence_elapsed = 0.0
        last_preview_time = 0.0
        last_preview_text = ""
        min_phrase_seconds = 0.7
        max_phrase_seconds = 12.0
        preview_interval_seconds = 1.2
        min_start_voiced_seconds = 0.12
        release_hysteresis = 0.80
        noise_floor = 0.0
        phrase_sequence = 0
        current_phrase_id = 0

        self.on_status("Listening")
        self.logger.info("Whisper worker listening for audio")
        while not self.stop_event.is_set():
            now = time.monotonic()
            try:
                chunk, rms = self.audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if not self.config.is_listening_enabled():
                phrase_chunks = []
                speech_active = False
                above_threshold_streak = 0
                voiced_chunk_count = 0
                voiced_seconds = 0.0
                silence_elapsed = 0.0
                last_preview_time = 0.0
                last_preview_text = ""
                current_phrase_id = 0
                self.on_partial("")
                self.on_status("Listening paused")
                continue

            threshold = self.config.get_threshold()
            if noise_floor == 0.0:
                noise_floor = min(rms, threshold)
            elif not speech_active:
                noise_floor = (noise_floor * 0.98) + (rms * 0.02)

            effective_threshold = max(threshold, noise_floor * 1.35)
            speaking = rms >= effective_threshold
            chunk_duration = chunk.size / self.sample_rate
            pre_roll_chunks.append(chunk)
            activated_this_chunk = False

            if speaking:
                above_threshold_streak += 1
            else:
                above_threshold_streak = 0

            required_start_chunks = max(1, int(np.ceil(min_start_voiced_seconds / max(chunk_duration, 1e-6))))
            if not speech_active and above_threshold_streak >= required_start_chunks:
                speech_active = True
                silence_elapsed = 0.0
                phrase_chunks = list(pre_roll_chunks)
                voiced_chunk_count = 0
                voiced_seconds = 0.0
                last_preview_text = ""
                phrase_sequence += 1
                current_phrase_id = phrase_sequence
                activated_this_chunk = True
                self.logger.info(
                    "Speech detected | phrase=%s rms=%.4f threshold=%.4f noise_floor=%.4f pre_roll_chunks=%s queue_depth=%s",
                    current_phrase_id,
                    rms,
                    effective_threshold,
                    noise_floor,
                    len(phrase_chunks),
                    self.audio_queue.qsize(),
                )

            if not speech_active:
                continue

            if not activated_this_chunk:
                phrase_chunks.append(chunk)
            if speaking:
                voiced_chunk_count += 1
                voiced_seconds += chunk_duration

            if rms < (effective_threshold * release_hysteresis):
                silence_elapsed += chunk_duration
            else:
                silence_elapsed = 0.0

            phrase = np.concatenate(phrase_chunks, dtype=np.float32)
            phrase_duration = phrase.size / self.sample_rate

            if (now - last_preview_time) >= preview_interval_seconds and phrase_duration >= 1.0:
                preview = self._transcribe(phrase)
                if preview:
                    last_preview_text = preview
                    self.logger.info(
                        "Partial transcript updated | phrase=%s duration=%.2fs voiced=%.2fs silence=%.2fs text=%r",
                        current_phrase_id,
                        phrase_duration,
                        voiced_seconds,
                        silence_elapsed,
                        preview,
                    )
                    self.on_partial(preview)
                last_preview_time = now

            should_finalize = (
                (silence_elapsed >= self.config.get_silence_timeout() and phrase_duration >= min_phrase_seconds)
                or (phrase_duration >= max_phrase_seconds)
            )
            if not should_finalize:
                continue

            text = ""
            should_transcribe = voiced_seconds >= min_start_voiced_seconds or bool(last_preview_text)
            self.logger.info(
                "Speech end detected | phrase=%s duration=%.2fs voiced=%.2fs silence=%.2fs preview=%s",
                current_phrase_id,
                phrase_duration,
                voiced_seconds,
                silence_elapsed,
                bool(last_preview_text),
            )
            if should_transcribe:
                self.on_status("Processing transcript...")
                text = self._transcribe(phrase)
                if not text and last_preview_text:
                    text = last_preview_text
                    self.logger.info("Final transcript fallback applied | phrase=%s source=preview", current_phrase_id)
            else:
                self.logger.info(
                    "Discarding phrase before final transcription | phrase=%s voiced=%.2fs chunks=%s",
                    current_phrase_id,
                    voiced_seconds,
                    len(phrase_chunks),
                )

            phrase_chunks = []
            speech_active = False
            above_threshold_streak = 0
            voiced_chunk_count = 0
            voiced_seconds = 0.0
            silence_elapsed = 0.0
            last_preview_time = 0.0
            last_preview_text = ""
            self.on_partial("")

            if text:
                self.logger.info("Final transcript generated | phrase=%s text=%r", current_phrase_id, text)
                self.on_final(text)
                try:
                    self.ollama_queue.put_nowait(PromptSubmission(phrase_id=current_phrase_id, text=text))
                    self.logger.info(
                        "Submission queued for LLM | phrase=%s queue_depth=%s",
                        current_phrase_id,
                        self.ollama_queue.qsize(),
                    )
                except queue.Full:
                    self.logger.warning("Ollama queue full; dropped latest prompt | phrase=%s", current_phrase_id)
            self.on_status("Listening")

    def _transcribe(self, audio: np.ndarray) -> str:
        try:
            result = self._get_model().transcribe(
                audio,
                language="en",
                fp16=False,
                verbose=False,
                temperature=0.0,
                condition_on_previous_text=False,
                no_speech_threshold=0.52,
                logprob_threshold=-1.0,
                compression_ratio_threshold=2.4,
            )
            return result.get("text", "").strip()
        except Exception:
            self.logger.exception("Whisper transcription error")
            return ""
