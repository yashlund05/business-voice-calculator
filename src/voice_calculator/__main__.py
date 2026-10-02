"""Entrypoint for `python -m voice_calculator`."""

import argparse
from pathlib import Path
import sys
import tkinter as tk

from voice_calculator.asr.vosk_engine import VoskEngine
from voice_calculator.config import VOSK_MODEL_PATH
from voice_calculator.controller import ListeningController
from voice_calculator.gui.app import VoiceCalculatorApp
from voice_calculator.logging_setup import setup_logging


def main() -> int:
    parser = argparse.ArgumentParser(description="Voice Calculator Desktop Application")
    parser.add_argument(
        "--model-path",
        type=str,
        default=str(VOSK_MODEL_PATH),
        help="Path to local Vosk model directory (default: models/vosk-model-small-en-us)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--console-log",
        action="store_true",
        help="Also output logs to console",
    )
    args = parser.parse_args()

    setup_logging(debug_mode=args.debug, console_output=args.console_log)

    engine = VoskEngine(model_path=Path(args.model_path))
    controller = ListeningController(engine=engine)

    root = tk.Tk()
    app = VoiceCalculatorApp(root=root, controller=controller)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
