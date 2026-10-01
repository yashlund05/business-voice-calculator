# Memory — Project Progress File

> **For the coding agent:** read this file FIRST every session; update it LAST every session (see `rules.md` §F). Keep it short: replace stale text, don't append forever. Never record anything here that was not actually done or measured.
> Other docs: `prd.md` (what), `architecture.md` (how), `phases.md` (order), `design.md` (UI), `research.md` (evidence), `rules.md` (constraints).

---

## 1. Project Status

- **Overall status:** Phase 3.1 (Dataset Recording Workflow & Consistency Verification) completed. 235 unit/mock tests passing, 1 integration test skipped pending local model download.
- **Last updated:** 2026-10-01 by Antigravity

## 2. Current Phase

- Phase: **Phase 3 — ASR Benchmark and Architecture Decision** (Subtask 3.1 dataset workflow validated and ready for recording).

## 3. Current Task

- Phase 3.1 dataset recording workflow validated. Next: User records real speech dataset using `tools/record_dataset.py`.

## 4. Completed Work

- Documentation pack created (`docs/prd.md`, `architecture.md`, `rules.md`, `phases.md`, `design.md`, `memory.md`, `research.md`).
- [0.1 Skeleton] Established virtual environment (Python 3.11.9), `.gitignore`, `pyproject.toml`, `requirements.txt`, `README.md`, package structure `src/voice_calculator/__init__.py`.
- [0.2 Config & logging] Implemented `config.py` constants and tunables, `logging_setup.py` with privacy-safe rotating file logging; added tests in `tests/test_config.py`, `tests/test_logging.py`, and `tests/test_smoke.py`.
- [1A Grammar Specification & Clarification] Defined formal grammar specification for 0–2000, unambiguous "and" / "a" rules, 1000–1999 structure, structural vs range error classification, normalization rules, reason codes, parser interface contract, and exhaustive testing plan.
- [1B Number Parser Implementation & Audit] Implemented `src/voice_calculator/numparse.py` with pure deterministic grammar parser, normalization, and reason code classification. Added `tests/test_numparse_cases.py` and `tests/test_numparse_exhaustive.py` (exhaustive 0–2000 canonical words, 0–2000 digit strings, boundary values, invariants, and fuzz testing).
- [1C Audio Input Foundation] Built `src/voice_calculator/audio/capture.py` providing `AudioFrame`, `AudioSource` protocol, `MicrophoneCapture` (via `sounddevice`), `FakeAudioSource`, and typed errors (`MicNotFound`, `MicLost`, `MicBusy`, `StreamError`). Added `tests/test_audio_capture.py` and `tools/check_mic.py`.
- [2.1 ASR Interface & WAV I/O] Implemented `ASREngine` protocol, `ASRResult` dataclass, typed exceptions (`ASRError`, `ModelMissingError`, `ModelLoadError`), and deterministic `FakeEngine` in `src/voice_calculator/asr/base.py`. Built strict 16 kHz mono int16 WAV reader/writer `src/voice_calculator/audio/wavio.py` using stdlib `wave`. Added `tests/test_asr_base.py` and `tests/test_wavio.py`.
- [2.2 Vosk Baseline Engine] Built `src/voice_calculator/asr/vosk_engine.py` integrating Vosk offline ASR with constrained number-word grammar, local model path configuration (`VOSK_MODEL_PATH`), explicit loading, typed error mapping, and uncalibrated confidence handling. Added `tests/test_vosk_engine.py` (10 unit tests + 1 model-skip integration test) and `tools/check_vosk.py`.
- [2.3 Vosk Baseline Evaluation & Benchmark Infrastructure] Implemented evaluation dataset schema, `labels.csv` loader, outcome classification (`CORRECT_ACCEPT`, `FALSE_ADDITION`, `CORRECT_REJECT`, `FALSE_REJECT`, `ERROR`), and metrics calculation engine in `src/voice_calculator/benchmark.py`. Built `tools/benchmark.py` (offline benchmark runner with category/speaker/split breakdowns and CSV export), `tools/record_dataset.py` (prompt-guided audio dataset recording helper), and `tools/transcribe.py` (WAV transcription CLI). Added `tests/test_benchmark.py` (20 unit/integration tests).
- [3.1 Real Speech Dataset Workflow & Prompt Alignment] Validated and expanded `tools/record_dataset.py` across 94 prompts covering units/teens (0-19), tens (20-90), confusable pairs (13/30..19/90), compound tens, hundreds variants, thousands/teen-hundreds, out-of-range, command words, conversational speech, and non-speech noise. Added category filtering, device selection, interactive re-record/skip controls, and automated prompt-to-parser grammar consistency tests in `tests/test_benchmark.py` (22 benchmark tests passing).

## 5. Current Architecture (as implemented)

- Architecture foundation laid per `architecture.md`.
- Modules that exist in code: `voice_calculator.config`, `voice_calculator.logging_setup`, `voice_calculator.numparse`, `voice_calculator.audio.capture`, `voice_calculator.audio.wavio`, `voice_calculator.asr.base`, `voice_calculator.asr.vosk_engine`, `voice_calculator.benchmark`.
- Chosen ASR engine: **Vosk small English + constrained grammar baseline** (pending Phase 3 benchmark evaluation and ADR).
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
| 10 | Vosk ASR baseline uses local model directory (never auto-downloaded) with constrained grammar (`DEFAULT_NUMBER_GRAMMAR`), setting uncalibrated confidence to None | 2026-10-01 | Phase 2.2 implementation |
| 11 | Benchmark harness classifies outcomes deterministically into CORRECT_ACCEPT, FALSE_ADDITION, CORRECT_REJECT, FALSE_REJECT; False Addition is the primary safety metric computed across all utterances | 2026-10-01 | Phase 2.3 implementation |
| 12 | Dataset recording prompts must strictly conform to parser grammar and research.md §3 coverage without altering parser grammar | 2026-10-01 | Phase 3.1 verification |

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

- Automated tests: **235 passed, 1 skipped** (`pytest -v`).
- Last test command/result: `.\.venv\Scripts\pytest.exe -v` -> 235 passed, 1 skipped in 1.38s (test_asr_base: 7, test_audio_capture: 9, test_benchmark: 22, test_config: 4, test_logging: 3, test_numparse_cases: 158, test_numparse_exhaustive: 10, test_smoke: 2, test_vosk_engine: 10 passed + 1 skipped, test_wavio: 10).
- Manual/CLI verification:
  - `tools/record_dataset.py --list-categories` verified (17 categories, 94 total prompts).
  - `tools/record_dataset.py --dry-run --count 5` verified.
  - `tools/benchmark.py` verified with synthetic dataset and CLI flags.

## 10. Benchmark Status

- **No live speech recordings run yet.** Benchmark harness, dataset recording helper, and reporting pipeline are fully implemented and verified with synthetic tests. Actual accuracy, latency, and resource metrics are pending real speech recording session.
- See `research.md` for metrics and templates.

## 11. Important Lessons

- Vosk model weights must never be downloaded automatically at runtime; checking local model existence and raising typed `ModelMissingError` ensures reliable offline behavior.
- Constraining Vosk grammar to the project's number-word closed vocabulary limits hallucination of general conversational words while leaving semantic parsing to `numparse.py`.
- Benchmark evaluation harness must treat False Addition (wrong number on valid audio or any number on negative audio) as the primary safety metric, and report the Rule-of-Three 95% upper bound when zero errors are observed.
- Automated prompt consistency tests ensure recording prompts never drift from the formal parser grammar.

## 12. Dependencies Added (with justification)

| Package | Version | Purpose | Why needed / alternative considered | Phase |
|---------|---------|---------|-------------------------------------|-------|
| pytest | 8.3.4 | Test framework | Automated unit and property testing; standard test runner | Phase 0 |
| sounddevice | 0.5.6 | Audio capture | Low-latency, reliable PortAudio Python bindings for Windows | Phase 1C |
| numpy | 2.4.6 | Buffer operations | Efficient audio buffer representation for sounddevice | Phase 1C |
| vosk | 0.3.45 | Offline ASR | Candidate ASR baseline engine for English speech recognition | Phase 2.2 |

## 13. Next Task

- **Phase 3 — Real Speech Dataset Recording**: Run `python tools/record_dataset.py` to record real speech utterances with the microphone to `data/recordings/` with `labels.csv`.

## 14. Files Changed Recently

- `tools/record_dataset.py` — modified — enhanced prompt coverage (94 prompts), category filtering, device index selection, re-record controls (Phase 3.1)
- `tests/test_benchmark.py` — modified — added prompt consistency and label CSV helper tests (Phase 3.1)
- `docs/memory.md` — modified — updated with Phase 3.1 status and test results

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
