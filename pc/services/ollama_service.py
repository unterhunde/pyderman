"""Streaming Ollama response worker."""

from __future__ import annotations

import json
import logging
import queue
import threading

import requests

from pc.services.prompt_submission import PromptSubmission


class OllamaService(threading.Thread):
    def __init__(
        self,
        ollama_queue: queue.Queue[PromptSubmission],
        stop_event: threading.Event,
        on_output_reset,
        on_output_append,
        on_status,
        url_getter,
        logger: logging.Logger,
        model_name: str,
    ) -> None:
        super().__init__(daemon=True)
        self.ollama_queue = ollama_queue
        self.stop_event = stop_event
        self.on_output_reset = on_output_reset
        self.on_output_append = on_output_append
        self.on_status = on_status
        self.url_getter = url_getter
        self.logger = logger
        self.model_name = model_name

    def run(self) -> None:
        while not self.stop_event.is_set():
            try:
                submission = self.ollama_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            prompt = submission.text
            self.logger.info(
                "Submission dequeued by LLM worker | phrase=%s queue_depth=%s",
                submission.phrase_id,
                self.ollama_queue.qsize(),
            )
            self.on_status("Ollama responding...")
            self.on_output_reset()
            self.on_output_append(f"Prompt: {prompt}\n\n")
            try:
                self.logger.info(
                    "LLM request started | phrase=%s model=%s url=%s",
                    submission.phrase_id,
                    self.model_name,
                    self.url_getter(),
                )
                response = requests.post(
                    self.url_getter(),
                    json={"model": self.model_name, "prompt": prompt, "stream": True},
                    stream=True,
                    timeout=120,
                )
                response.raise_for_status()
                first_token_logged = False
                for line in response.iter_lines():
                    if self.stop_event.is_set():
                        break
                    if not line:
                        continue
                    payload = json.loads(line.decode("utf-8"))
                    token = payload.get("response", "")
                    if token:
                        if not first_token_logged:
                            self.logger.info("LLM response received | phrase=%s", submission.phrase_id)
                            first_token_logged = True
                        self.on_output_append(token)
                    if payload.get("done", False):
                        self.logger.info("LLM stream completed | phrase=%s", submission.phrase_id)
                        break
            except Exception:
                self.logger.exception("Ollama stream error | phrase=%s", submission.phrase_id)
                self.on_output_append("\n[Ollama error]\n")
            finally:
                self.on_output_append("\n")
                self.on_status("Listening")
