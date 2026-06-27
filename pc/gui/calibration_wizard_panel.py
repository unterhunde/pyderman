"""Tkinter panel for the AUDIO-001 calibration wizard Phase A shell."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from pc.services.calibration_metrics_provider import SimulatedCalibrationMetricsProvider
from pc.services.calibration_session_controller import (
    CalibrationSessionController,
    CalibrationWizardViewState,
    InvalidTransitionError,
    WizardScheduler,
)


class _TkAfterScheduler(WizardScheduler):
    def __init__(self, root: tk.Misc) -> None:
        self._root = root

    def call_later(self, delay_ms: int, callback):
        return self._root.after(delay_ms, callback)

    def cancel(self, handle) -> None:
        try:
            self._root.after_cancel(handle)
        except tk.TclError:
            return


class CalibrationWizardPanel(ttk.Frame):
    def __init__(self, parent: ttk.Frame, root: tk.Misc, logger: logging.Logger | None = None) -> None:
        super().__init__(parent, style="Panel.TFrame", padding=10)
        self._root = root
        self._logger = logger or logging.getLogger("pibot.console.calibration")
        self._build_ui()
        scheduler = _TkAfterScheduler(root)
        self._controller = CalibrationSessionController(
            metrics_provider=SimulatedCalibrationMetricsProvider(),
            scheduler=scheduler,
            on_update=self._apply_view_state,
        )

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        header = ttk.LabelFrame(self, text="Calibration Wizard", padding=10)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        self.phrase_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            header,
            text="Enable optional phrase-test stage",
            variable=self.phrase_enabled_var,
        ).grid(row=0, column=0, sticky="w")
        self.progress_label = ttk.Label(header, text="Progress: 0/7", style="Help.TLabel")
        self.progress_label.grid(row=0, column=1, sticky="e")
        self.progress_bar = ttk.Progressbar(header, orient="horizontal", mode="determinate", maximum=7, value=0)
        self.progress_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        stage = ttk.LabelFrame(self, text="Operator Cues", padding=10)
        stage.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        stage.grid_columnconfigure(1, weight=1)
        ttk.Label(stage, text="Stage").grid(row=0, column=0, sticky="w")
        self.stage_name_value = ttk.Label(stage, text="Idle", style="Header.TLabel")
        self.stage_name_value.grid(row=0, column=1, sticky="w")
        ttk.Label(stage, text="Instruction").grid(row=1, column=0, sticky="nw", pady=(8, 0))
        self.instruction_value = ttk.Label(stage, text="", wraplength=520, justify="left")
        self.instruction_value.grid(row=1, column=1, sticky="w", pady=(8, 0))
        ttk.Label(stage, text="Cue").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.cue_value = ttk.Label(stage, text="idle", style="Warn.TLabel")
        self.cue_value.grid(row=2, column=1, sticky="w", pady=(8, 0))
        ttk.Label(stage, text="Countdown").grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.countdown_value = ttk.Label(stage, text="0s", style="Warn.TLabel")
        self.countdown_value.grid(row=3, column=1, sticky="w", pady=(8, 0))
        self.status_message_value = ttk.Label(stage, text="", style="Help.TLabel", wraplength=640, justify="left")
        self.status_message_value.grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))

        actions = ttk.LabelFrame(self, text="Actions", padding=10)
        actions.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        for idx in range(5):
            actions.grid_columnconfigure(idx, weight=1)
        self.start_btn = ttk.Button(actions, text="Start Wizard", command=self._on_start_wizard, style="Accent.TButton")
        self.start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.start_stage_btn = ttk.Button(actions, text="Start Stage", command=self._on_start_stage)
        self.start_stage_btn.grid(row=0, column=1, sticky="ew", padx=(0, 6))
        self.repeat_btn = ttk.Button(actions, text="Repeat Stage", command=self._on_repeat_stage)
        self.repeat_btn.grid(row=0, column=2, sticky="ew", padx=(0, 6))
        self.next_btn = ttk.Button(actions, text="Next Stage", command=self._on_next_stage)
        self.next_btn.grid(row=0, column=3, sticky="ew", padx=(0, 6))
        self.cancel_btn = ttk.Button(actions, text="Cancel", command=self._on_cancel)
        self.cancel_btn.grid(row=0, column=4, sticky="ew")
        self.close_btn = ttk.Button(actions, text="Close", command=self._on_close)
        self.close_btn.grid(row=1, column=4, sticky="ew", pady=(8, 0))

        results = ttk.LabelFrame(self, text="Results Summary", padding=10)
        results.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        results.grid_columnconfigure(0, weight=1)
        self.results_value = ttk.Label(results, text="No captures yet.", justify="left", wraplength=760)
        self.results_value.grid(row=0, column=0, sticky="w")

        diagnostics = ttk.LabelFrame(self, text="Advanced Diagnostics", padding=10)
        diagnostics.grid(row=4, column=0, sticky="nsew", pady=(10, 0))
        diagnostics.grid_columnconfigure(0, weight=1)
        self.toggle_drawer_btn = ttk.Button(
            diagnostics,
            text="Show Diagnostics Drawer",
            command=self._toggle_drawer,
        )
        self.toggle_drawer_btn.grid(row=0, column=0, sticky="w")
        self.drawer = ttk.Frame(diagnostics, style="Panel.TFrame")
        self.drawer.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.drawer.grid_columnconfigure(1, weight=1)
        self._drawer_visible = False
        self.drawer.grid_remove()
        self._diag_labels: dict[str, ttk.Label] = {}
        fields = [
            ("raw_rms", "Raw RMS"),
            ("processed_rms", "Processed RMS"),
            ("peak", "Peak"),
            ("clipping", "Clipping"),
            ("gate_ratio", "Gate Ratio"),
            ("agc_gain", "AGC Gain"),
            ("capture_success", "Capture Success"),
        ]
        for row, (key, label) in enumerate(fields):
            ttk.Label(self.drawer, text=label).grid(row=row, column=0, sticky="w")
            value = ttk.Label(self.drawer, text="-", style="Help.TLabel")
            value.grid(row=row, column=1, sticky="w")
            self._diag_labels[key] = value

    def _toggle_drawer(self) -> None:
        self._drawer_visible = not self._drawer_visible
        if self._drawer_visible:
            self.drawer.grid()
            self.toggle_drawer_btn.configure(text="Hide Diagnostics Drawer")
        else:
            self.drawer.grid_remove()
            self.toggle_drawer_btn.configure(text="Show Diagnostics Drawer")

    def _invoke(self, fn) -> None:
        try:
            fn()
        except InvalidTransitionError as exc:
            self._logger.warning("Calibration action rejected: %s", exc)

    def _on_start_wizard(self) -> None:
        self._invoke(lambda: self._controller.start_wizard(phrase_enabled=self.phrase_enabled_var.get()))

    def _on_start_stage(self) -> None:
        self._invoke(self._controller.start_stage)

    def _on_repeat_stage(self) -> None:
        self._invoke(self._controller.repeat_stage)

    def _on_next_stage(self) -> None:
        self._invoke(self._controller.next_step)

    def _on_cancel(self) -> None:
        self._controller.cancel()

    def _on_close(self) -> None:
        self._invoke(self._controller.close)

    def _apply_view_state(self, view_state: CalibrationWizardViewState) -> None:
        self.stage_name_value.configure(text=view_state.stage_name)
        self.instruction_value.configure(text=view_state.instruction)
        cue_style = "Warn.TLabel"
        if view_state.cue == "start":
            cue_style = "StatusValue.TLabel"
        elif view_state.cue == "stop":
            cue_style = "Danger.TLabel"
        self.cue_value.configure(text=view_state.cue.upper(), style=cue_style)
        self.countdown_value.configure(text=f"{view_state.countdown_seconds}s")
        self.status_message_value.configure(text=view_state.status_message)
        self.progress_bar.configure(maximum=max(view_state.progress_total, 1), value=view_state.progress_current)
        self.progress_label.configure(text=f"Progress: {view_state.progress_current}/{view_state.progress_total}")

        self.start_btn.state(["!disabled"] if view_state.state.value in {"IDLE", "COMPLETE", "FAILED", "CANCELLED"} else ["disabled"])
        self.start_stage_btn.state(["!disabled"] if view_state.can_start and view_state.state.value not in {"IDLE"} else ["disabled"])
        self.repeat_btn.state(["!disabled"] if view_state.can_repeat else ["disabled"])
        self.next_btn.state(["!disabled"] if view_state.can_next else ["disabled"])
        self.cancel_btn.state(["!disabled"] if view_state.can_cancel else ["disabled"])
        self.close_btn.state(["!disabled"] if view_state.can_close else ["disabled"])

        if view_state.stage_results:
            lines = []
            for stage, metrics in view_state.stage_results.items():
                lines.append(
                    (
                        f"{stage.value.title()}: raw={metrics.raw_rms:.4f}, proc={metrics.processed_rms:.4f}, "
                        f"peak={metrics.peak:.3f}, clip={metrics.clipping:.3f}, gate={metrics.gate_ratio:.3f}, "
                        f"agc={metrics.agc_gain:.3f}, success={metrics.capture_success}"
                    )
                )
            self.results_value.configure(text="\n".join(lines))
        else:
            self.results_value.configure(text="No captures yet.")

        latest = view_state.latest_metrics
        if latest is None:
            for label in self._diag_labels.values():
                label.configure(text="-")
            return
        self._diag_labels["raw_rms"].configure(text=f"{latest.raw_rms:.4f}")
        self._diag_labels["processed_rms"].configure(text=f"{latest.processed_rms:.4f}")
        self._diag_labels["peak"].configure(text=f"{latest.peak:.4f}")
        self._diag_labels["clipping"].configure(text=f"{latest.clipping:.4f}")
        self._diag_labels["gate_ratio"].configure(text=f"{latest.gate_ratio:.4f}")
        self._diag_labels["agc_gain"].configure(text=f"{latest.agc_gain:.4f}")
        self._diag_labels["capture_success"].configure(text="yes" if latest.capture_success else "no")
