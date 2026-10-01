# Memory — Project Progress File

> **For the coding agent:** read this file FIRST every session; update it LAST every session (see `rules.md` §F). Keep it short: replace stale text, don't append forever. Never record anything here that was not actually done or measured.
> Other docs: `prd.md` (what), `architecture.md` (how), `phases.md` (order), `design.md` (UI), `research.md` (evidence), `rules.md` (constraints).

---

## 1. Project Status

- **Overall status:** Phase 2.1 (ASR Interface and WAV I/O) completed. All 203 automated unit tests passing.
- **Last updated:** 2026-10-01 by Antigravity

## 2. Current Phase

- Phase: **Phase 2 — ASR Interface and Prerecorded-Audio Baseline** (Subtask 2.1 completed; ready for Subtask 2.2).

## 3. Current Task

- Phase 2.1 completed. Next: Phase 2, subtask 2.2 (`asr/vosk_engine.py` baseline implementation).

## 4. Completed Work

- Documentation pack created (`docs/prd.md`, `architecture.md`, `rules.md`, `phases.md`, `design.md`, `memory.md`, `research.md`).
- [0.1 Skeleton] Established virtual environment (Python 3.11.9), `.gitignore`, `pyproject.toml`, `requirements.txt`, `README.md`, package structure `src/voice_calculator/__init__.py`.
- [0.2 Config & logging] Implemented `config.py` constants and tunables, `logging_setup.py` with privacy-safe rotating file logging; added tests in `tests/test_config.py`, `tests/test_logging.py`, and `tests/test_smoke.py`.
- [1A Grammar Specification & Clarification] Defined formal grammar specification for 0–2000, unambiguous "and" / "a" rules, 1000–1999 structure, structural vs range error classification, normalization rules, reason codes, parser interface contract, and exhaustive testing plan.
- [1B Number Parser Implementation & Audit] Implemented `src/voice_calculator/numparse.py` with pure deterministic grammar parser, normalization, and reason code classification. Added `tests/test_numparse_cases.py` and `tests/test_numparse_exhaustive.py` (exhaustive 0–2000 canonical words, 0–2000 digit strings, boundary values, invariants, and fuzz testing).
- [1C Audio Input Foundation] Built `src/voice_calculator/audio/capture.py` providing `AudioFrame`, `AudioSource` protocol, `MicrophoneCapture` (via `sounddevice`), `FakeAudioSource`, and typed errors (`MicNotFound`, `MicLost`, `MicBusy`, `StreamError`). Added `tests/test_audio_capture.py` and `tools/check_mic.py`.
- [2.1 ASR Interface & WAV I/O] Implemented `ASREngine` protocol, `ASRResult` dataclass, typed exceptions (`ASRError`, `ModelMissingError`, `ModelLoadError`), and deterministic `FakeEngine` in `src/voice_calculator/asr/base.py`. Built strict 16 kHz mono int16 WAV reader/writer `src/voice_calculator/audio/wavio.py` using stdlib `wave`. Added `tests/test_asr_base.py` and `tests/test_wavio.py`.

## 5. Current Architecture (as implemented)

- Architecture foundation laid per `architecture.md`.
- Modules that exist in code: `voice_calculator.config`, `voice_calculator.logging_setup`, `voice_calculator.numparse`, `voice_calculator.audio.capture`, `voice_calculator.audio.wavio`, `voice_calculator.asr.base`.
- Chosen ASR engine: **none yet** (baseline plan: Vosk + constrained grammar, pending Phase 3 ADR; `FakeEngine` available for testing).
- VAD: **none yet** (plan: energy baseline).
- Auto-accept policy: **off** (confirm-all) by default (`AUTO_ACCEPT_ENABLED = False`).

## 6. Confirmed Decisions

| # | Decision | Date | Source/Reason |
|---|----------|------|---------------|
| 1 | Windows desktop, Python, offline, English, 0–2000, addition only, buttons only, no voice commands | 2026-10-01 | `prd.md` (FIXED requirements) |
| 2 | Parser and arithmetic are deterministic; no LLM | 2026-10-01 | `rules.md` §C |
| 3 | Uncertain recognition is never silently added; default policy is confirm-all until calibrated | 2026-10-01 | `architecture.md` §9 |
| 4 | Tkinter GUI; worker thread + queue model | 2026-10-01 | `architecture.md` §11 |
| 5 | Python 3.11.9 runtime and pytest 8.3.4 testing framework | 2026-10-01 | Phase 0 verification |
| 6 | Number grammar accepts canonical 0–2000, "a hundred/thousand", teen-hundreds (1100–1999), and canonical digit strings; British/Indian English optional "and" constructions; structural scale errors are MALFORMED; valid numbers >2000 evaluate to OUT_OF_RANGE | 2026-10-01 | Phase 1A clarification |
| 7 | Parser is pure and deterministic: normalization strips harmless trailing `. ? !`, rejects internal punctuation, evaluates explicit grammar without token accumulation | 2026-10-01 | Phase 1B implementation |
| 8 | Audio capture uses sounddevice (16 kHz mono int16) with bounded queue and non-blocking callback; hardware-independent tests use FakeAudioSource and mocks | 2026-10-01 | Phase 1C implementation |
| 9 | ASR engine abstraction uses ASREngine protocol and ASRResult dataclass; WAV I/O uses stdlib wave strictly validated to 16 kHz mono int16 PCM | 2026-10-01 | Phase 2.1 implementation |

## 7. Pending Decisions

| # | Question | Default for now | Resolve in |
|---|----------|-----------------|-----------|
| P1 | Python version | **Resolved: 3.11.9** | Phase 0 |
| P2 | ASR engine/model (Vosk, faster-whisper size, hybrid) | Vosk + grammar baseline | Phase 3 ADR |
| P3 | VAD choice and timings | energy VAD | Phase 4 |
| P4 | Auto-accept rules/thresholds | none (confirm-all) | Phase 5 |
| P5 | Ratify PROVISIONAL targets in `prd.md` §13 | as written | Phase 3 gate |
| P6 | Accept "fifteen hundred and fifty"-style forms | **Resolved: Accepted** | Phase 1A |
| P7 | Multiple numbers per utterance | reject | Post-MVP |
| P8 | Zero requires confirm | yes | after benchmark |
| P9 | PyInstaller one-folder vs one-file | one-folder | Phase 8 |

## 8. Known Bugs

- None recorded.

## 9. Test Status

- Automated tests: **203 passed** (`pytest -v`).
- Last test command/result: `.\.venv\Scripts\pytest.exe -v` -> 203 passed in 1.30s (test_asr_base: 7, test_audio_capture: 9, test_config: 4, test_logging: 3, test_numparse_cases: 158, test_numparse_exhaustive: 10, test_smoke: 2, test_wavio: 10).
- Manual tests: `tools/check_mic.py` verified live device enumeration and 16 kHz stream capture on Windows.

## 10. Benchmark Status

- **No benchmarks run. No accuracy, latency, or resource numbers exist.** Dataset not yet recorded.
- See `research.md` for templates.

## 11. Important Lessons

- WAV format validation using stdlib `wave` ensures offline compatibility with zero extra audio file dependencies.
- `FakeEngine` cleanly decouples test execution from external ML binaries, keeping all automated testing fast, deterministic, and hardware-independent.

## 12. Dependencies Added (with justification)

| Package | Version | Purpose | Why needed / alternative considered | Phase |
|---------|---------|---------|-------------------------------------|-------|
| pytest | 8.3.4 | Test framework | Automated unit and property testing; standard test runner | Phase 0 |
| sounddevice | 0.5.6 | Audio capture | Low-latency, reliable PortAudio Python bindings for Windows | Phase 1C |
| numpy | 2.4.6 | Buffer operations | Efficient audio buffer representation for sounddevice | Phase 1C |

## 13. Next Task

- **Phase 2, subtask 2.2 — Vosk baseline** (`phases.md`): `VoskEngine` with constrained number-word grammar, local model path from config, no auto-download, clear `ModelMissingError`, test with fake/skip marker when model absent.

## 14. Files Changed Recently

- `src/voice_calculator/asr/base.py` — new — ASREngine protocol, ASRResult dataclass, FakeEngine (Phase 2.1)
- `src/voice_calculator/asr/__init__.py` — new — ASR package exports (Phase 2.1)
- `src/voice_calculator/audio/wavio.py` — new — WAV read/write helper for 16 kHz mono 16-bit PCM (Phase 2.1)
- `tests/test_asr_base.py` — new — unit tests for ASR abstraction & FakeEngine (Phase 2.1)
- `tests/test_wavio.py` — new — unit tests for WAV read/write & format rejection (Phase 2.1)
- `src/voice_calculator/audio/__init__.py` — modified — exported wavio helpers (Phase 2.1)
- `docs/memory.md` — modified — updated with Phase 2.1 completion and test results

## 15. Do Not Change Casually (requires explicit user approval)

- FIXED requirements in `prd.md`: offline, English, 0–2000, addition only, physical Start/Stop buttons, no voice commands, local-only processing.
- Parser accepted/rejected grammar in `prd.md` §7 (changes require updating tests and docs together).
- "Never silently add uncertain recognition" and the confirm-by-default policy.
- Rule that parsing/arithmetic are deterministic (no LLM/ML).
- Thread model: no Tk calls off the main thread; audio/ASR off the GUI thread.
- Calculator total derived from entries (single source of truth).
- Thresholds in `config.py` (change only with evidence in `research.md`).
- Privacy defaults: no audio saved, no values/transcripts logged by default, no network.

## 16. Session Update Checklist (agent)

- [x] Status/phase/task updated
- [x] Completed work and files changed listed
- [x] Test status reflects what was *actually run*
- [x] New decisions, bugs, dependencies, lessons recorded
- [x] Next task set (one subtask)
