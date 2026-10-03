# Voice Calculator

An offline Windows desktop application designed to continuously recognize spoken English numbers (0–2000) and add them to a running total.

## Quick Start (Development)

1. Create and activate a Python 3.11+ virtual environment:
   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install development dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

3. Run the automated test suite:
   ```powershell
   pytest
   ```

## Packaging (Windows, one-folder — ADR-005)

Build a portable, fully offline distribution (no Python required on the target machine):

1. Ensure the local Vosk model exists at `models/vosk-model-small-en-us` (never downloaded automatically), and install the build tool:
   ```powershell
   pip install -r requirements.txt pyinstaller
   ```

2. Build from the repository root:
   ```powershell
   .\.venv\Scripts\pyinstaller.exe --noconfirm --distpath dist --workpath build build_spec\voice_calculator.spec
   ```

3. Verify the bundle (layout, bundled model, native DLLs, frozen-path resolution, GUI launch smoke):
   ```powershell
   .\.venv\Scripts\python.exe tools\verify_package.py --dist dist\VoiceCalculator
   ```

4. Distribute the **whole folder** `dist\VoiceCalculator\` — extract or copy it to a
   user-writable location (e.g. Desktop or Documents, not Program Files) and run
   `VoiceCalculator.exe`. Logs are written to a `logs\` folder next to the exe.
   The app is fully offline: it makes no network connections and ships its own
   speech model (ADR-001: Vosk small English with a constrained number grammar).

## Documentation

Project documentation is located in `docs/`:
- `docs/prd.md` — Product Requirements Document
- `docs/architecture.md` — Technical Architecture & Component Design
- `docs/rules.md` — Coding Agent Constitution and Rules
- `docs/phases.md` — Implementation Roadmap & Phase Gates
- `docs/design.md` — UI/UX Specification
- `docs/memory.md` — Project Progress & State File
- `docs/research.md` — Experiment & Benchmark Records
