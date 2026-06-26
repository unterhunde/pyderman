#!/usr/bin/env python3
"""PC composition root for the PiBot operator console."""

from __future__ import annotations

import sys
from pathlib import Path
import tkinter as tk

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from pibot_config import load_settings
from pc.operator_console_app import OperatorConsoleApp


def create_application(root: tk.Tk) -> OperatorConsoleApp:
    settings = load_settings()
    return OperatorConsoleApp(root=root, settings=settings)


def main() -> None:
    root = tk.Tk()
    app = create_application(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()

