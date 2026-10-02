"""Voice Calculator top-level entrypoint.

Run with:
    python main.py
"""

from pathlib import Path
import sys

# Ensure src/ is on the Python module search path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from voice_calculator.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
