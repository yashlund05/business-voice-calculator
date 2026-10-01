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

## Documentation

Project documentation is located in `docs/`:
- `docs/prd.md` — Product Requirements Document
- `docs/architecture.md` — Technical Architecture & Component Design
- `docs/rules.md` — Coding Agent Constitution and Rules
- `docs/phases.md` — Implementation Roadmap & Phase Gates
- `docs/design.md` — UI/UX Specification
- `docs/memory.md` — Project Progress & State File
- `docs/research.md` — Experiment & Benchmark Records
