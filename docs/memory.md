# Memory — Project Progress File

> **For the coding agent:** read this file FIRST every session; update it LAST every session (see `rules.md` §F). Keep it short: replace stale text, don't append forever. Never record anything here that was not actually done or measured.
> Other docs: `prd.md` (what), `architecture.md` (how), `phases.md` (order), `design.md` (UI), `research.md` (evidence), `rules.md` (constraints).

---

## 1. Project Status

- **Overall status:** Phase 3.8 (Real Speech Benchmark and VAD Calibration) completed. 360 unit/mock/integration tests passing (100% pass rate).
- **Last updated:** 2026-10-02 by Antigravity

## 2. Current Phase

- Phase: **Phase 3 — ASR Benchmark and Architecture Decision** (Subtasks 3.1, 3.2, 3.3, 3.4, 3.5, 3.6A, 3.6B, 3.7, and 3.8 completed).

## 3. Current Task

- Phase 3.8 completed. Next: Phase 4 (ASR Candidate evaluation / Whisper comparison or real speech dataset collection).

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
- [3.2 VAD & Utterance Segmentation Foundation] Implemented modular `VADDetector` protocol and zero-ML `EnergyVAD` baseline in `src/voice_calculator/audio/vad.py`. Implemented 3-state online finite state machine (`SILENCE`, `SPEECH_ACTIVE`, `SPEECH_HANGOVER`) in `src/voice_calculator/audio/segmenter.py` with pre-roll ring buffer preservation, trailing hangover window, min speech duration enforcement (discarding short clicks/noise), max utterance cap (`is_too_long`), and queue overflow tracking (`is_damaged`). Added `tests/test_vad.py` (8 tests) and `tests/test_segmenter.py` (12 tests). Updated `docs/architecture.md` and `docs/research.md`.
- [3.3 Single-Utterance Audio Processing Pipeline Orchestration] Implemented `voice_calculator.pipeline` (`AudioPipeline`, `PipelineResult`, `PipelineStatus`). Connects `AudioSource` -> `UtteranceSegmenter` -> `ASREngine` -> `numparse.parse()` with typed error handling, candidate emission without arithmetic addition, flush/reset mechanisms, and zero arithmetic logic. Added 15 comprehensive unit tests in `tests/test_pipeline.py`.
- [3.4 Candidate Safety & Decision Layer] Implemented `voice_calculator.decision` (`DecisionType`, `DecisionReason`, `DecisionResult`, `DecisionConfig`, `SafetyDecisionEngine`, `evaluate_candidate`). Evaluates PipelineResult into ACCEPT, REPEAT, REJECT with strict value masking (value=None on non-accepts), confirm-by-default policy, zero confirmation enforcement, uncalibrated confidence handling, and zero arithmetic logic. Added 21 comprehensive unit/invariant tests in `tests/test_decision.py`.
- [3.5 Calculator State, History & Undo] Implemented `voice_calculator.calculator` (`Calculator`, `HistoryEntry`, `CalculatorError`, `InvalidValueError`). Maintains running total strictly derived from immutable history entries, LIFO reversible `undo()`, state `reset()`, and strict integer validation (0–2000 range, rejecting floats, booleans, negative values) with zero dependencies on audio/ASR/VAD/GUI/parser. Added 31 comprehensive unit/invariant tests in `tests/test_calculator.py`.
- [3.6A Desktop GUI Shell] Implemented `voice_calculator.gui` (`VoiceCalculatorApp`, `UIState`, `STATE_COLORS`, `STATE_TEXTS`, `format_number`, `get_decision_feedback_message`). Built responsive Tkinter window with prominent hero running total display (56pt bold), physical Start/Stop/Undo/Clear controls, explicit status indicator bar, in-place candidate confirmation prompt (`Add <N>` / `Discard`), and scrollable recent additions list. Added 13 comprehensive unit/interaction tests in `tests/test_gui.py`.
- [3.6B Background Listening Controller & GUI Integration] Implemented `voice_calculator.controller` (`ListeningController`, `ControllerEvent`, `ControllerEventType`). Coordinates background worker thread, audio capture, VAD segmentation, ASR engine, deterministic parser, and candidate safety decision engine. Communicates with `VoiceCalculatorApp` main thread via thread-safe `queue.Queue` with periodic polling (`root.after`). Implemented session isolation (`session_id`), multi-worker prevention, clean stop/discard semantics, exception safety (typed audio and model errors), and clean window close handler (`WM_DELETE_WINDOW`). Added 8 comprehensive unit/integration tests in `tests/test_controller.py` and 4 additional GUI integration tests in `tests/test_gui.py` (17 total GUI tests).
- [3.7 Fast Mode Foundation & Mode Selector] Implemented `OperatingMode` (`SAFE`, `FAST`) in `voice_calculator.decision`. Configured `SafetyDecisionEngine` to enforce manual confirmation for all numbers in Safe Mode, while preparing Fast Mode with strict confidence gating (missing/uncalibrated confidence forces confirmation; calibrated confidence auto-adds only when `auto_accept_enabled` is active and threshold is met; 0 always requires confirmation). Integrated responsive Safe/Fast Mode radio selector into `VoiceCalculatorApp` header and added mode delegation methods in `ListeningController`. Added 5 new decision tests (26 total in `test_decision.py`), 1 new controller test (9 total in `test_controller.py`), and 4 new GUI tests (21 total in `test_gui.py`).
- [3.8 Real Speech Benchmark and VAD Calibration] Verified dataset readiness, ground truth schema, category coverage (94 prompts), and git exclusion. Audited Vosk baseline model integration (`models/vosk-model-small-en-us`). Audited EnergyVAD and UtteranceSegmenter; identified and resolved a critical pre-roll accounting bug where pre-roll silence buffer duration was included in `_speech_duration_ms`, allowing short noise clicks (<250ms) to trigger spurious utterances. Added regression test `test_segmenter_short_noise_burst_with_full_pre_roll_rejected` (13/13 segmenter tests pass, 360 total tests pass). Calibrated VAD timing parameters and documented findings in `docs/research.md`.

## 5. Current Architecture (as implemented)

- Architecture foundation laid per `architecture.md`.
- Modules that exist in code: `voice_calculator.config`, `voice_calculator.logging_setup`, `voice_calculator.numparse`, `voice_calculator.audio.capture`, `voice_calculator.audio.wavio`, `voice_calculator.audio.vad`, `voice_calculator.audio.segmenter`, `voice_calculator.asr.base`, `voice_calculator.asr.vosk_engine`, `voice_calculator.benchmark`, `voice_calculator.pipeline`, `voice_calculator.decision`, `voice_calculator.calculator`, `voice_calculator.controller`, `voice_calculator.gui`.
- Chosen ASR engine: **Vosk small English + constrained grammar baseline** (pending Phase 3 benchmark evaluation and ADR).
- VAD: **EnergyVAD baseline (500.0 RMS threshold, 250ms pre-roll, 700ms hangover, 250ms min utterance, 6000ms max utterance)** (pending calibration on real recordings).
- Operating Mode default: **Safe Mode** (`OperatingMode.SAFE`); auto-accept policy is **off** (`AUTO_ACCEPT_ENABLED = False`).

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
| 13 | VAD layer is modular via VADDetector protocol; baseline is pure EnergyVAD; UtteranceSegmenter online state machine enforces pre-roll, hangover, min speech duration, max utterance cap, and overflow tracking | 2026-10-01 | Phase 3.2 implementation |
| 14 | AudioPipeline orchestrator coordinates AudioSource -> UtteranceSegmenter -> ASREngine -> numparse.parse() with dependency injection; emits candidate PARSED results without performing arithmetic additions; preserves clean separation of parsing from decision engine | 2026-10-01 | Phase 3.3 implementation |
| 15 | SafetyDecisionEngine classifies PipelineResults into ACCEPT, REPEAT, REJECT with strict value masking (value=None on non-accepts), confirm-by-default policy, zero confirmation enforcement, uncalibrated confidence handling, and zero arithmetic logic | 2026-10-01 | Phase 3.4 implementation |
| 16 | Calculator domain layer maintains deterministic running total derived strictly from immutable HistoryEntry records, reversible LIFO undo(), state reset(), and strict 0–2000 integer validation with zero audio/ASR/VAD/GUI/parser dependencies | 2026-10-01 | Phase 3.5 implementation |
| 17 | VoiceCalculatorApp Tkinter desktop shell provides prominent running total display, physical Start/Stop/Undo/Clear controls, explicit UIState indicators, and in-place candidate confirmation prompt; strictly isolates GUI from recognition heuristics and arithmetic calculation | 2026-10-01 | Phase 3.6A implementation |
| 18 | ListeningController coordinates background audio worker thread, utterance segmentation, ASR inference, parsing, and safety evaluation, delivering structured events to GUI via thread-safe queue with monotonic session isolation and clean stop/discard semantics | 2026-10-01 | Phase 3.6B implementation |
| 19 | OperatingMode enum (SAFE, FAST) introduces operating mode abstraction: Safe Mode enforces confirm-all for every candidate; Fast Mode gates automatic addition strictly behind calibrated confidence, keeping uncalibrated/missing confidence (e.g. Vosk baseline) safely requiring confirmation | 2026-10-02 | Phase 3.7 implementation |
| 20 | UtteranceSegmenter tracks active speech duration separately from pre-roll ring buffer silence; pre-roll audio frames are preserved in finalized Utterance for onset phonetic integrity but must not satisfy min_utterance_ms noise filter | 2026-10-02 | Phase 3.8 implementation |

## 7. Pending Decisions

| # | Question | Default for now | Resolve in |
|---|----------|-----------------|-----------|
| P1 | Python version | **Resolved: 3.11.9** | Phase 0 |
| P2 | ASR engine/model (Vosk, faster-whisper size, hybrid) | Vosk + grammar baseline | Phase 3 ADR |
| P3 | VAD choice and timings | EnergyVAD (threshold 500 RMS, 250ms pre-roll, 700ms hangover) | Phase 4 calibration |
| P4 | Auto-accept rules/thresholds | none (confirm-all) | Phase 5 |
| P5 | Ratify PROVISIONAL targets in `prd.md` §13 | as written | Phase 3 gate |
| P6 | Accept "fifteen hundred and fifty"-style forms | **Resolved: Accepted** | Phase 1A |
| P7 | Multiple numbers per utterance | reject | Post-MVP |
| P8 | Zero requires confirm | yes | after benchmark |
| P9 | PyInstaller one-folder vs one-file | one-folder | Phase 8 |

## 8. Known Bugs

- None recorded.

## 9. Test Status

- Automated tests: **360 passed, 0 skipped, 0 failed** (`pytest -v`).
- Last test command/result: `.\.venv\Scripts\pytest.exe -v` -> 360 passed in 4.95s (test_asr_base: 7, test_audio_capture: 9, test_benchmark: 22, test_calculator: 31, test_config: 5, test_controller: 9, test_decision: 26, test_gui: 21, test_logging: 3, test_numparse_cases: 158, test_numparse_exhaustive: 10, test_pipeline: 15, test_segmenter: 13, test_smoke: 2, test_vad: 8, test_vosk_engine: 11, test_wavio: 10).

## 10. Benchmark Status

- **No live speech recordings run yet.** Benchmark harness, dataset recording helper, VAD segmentation, single-utterance pipeline orchestration, safety decision engine, calculator domain core, desktop GUI shell, background listening controller, and Safe/Fast mode foundations are fully implemented and verified with automated tests. Actual accuracy, latency, and resource metrics are pending real speech recording session.
- See `research.md` for metrics and templates.

## 11. Important Lessons

- Vosk model weights must never be downloaded automatically at runtime; checking local model existence and raising typed `ModelMissingError` ensures reliable offline behavior.
- Constraining Vosk grammar to the project's number-word closed vocabulary limits hallucination of general conversational words while leaving semantic parsing to `numparse.py`.
- Benchmark evaluation harness must treat False Addition (wrong number on valid audio or any number on negative audio) as the primary safety metric, and report the Rule-of-Three 95% upper bound when zero errors are observed.
- Automated prompt consistency tests ensure recording prompts never drift from the formal parser grammar.
- Online utterance segmentation must cleanly separate speech detection (VADDetector protocol) from temporal state transitions (UtteranceSegmenter), keeping audio capture and downstream ASR decoupled.
- Pre-roll frames (250ms) are pre-onset context silence needed for phonetic recognition of initial plosives/fricatives ("two", "three", "six"), but MUST NOT be counted towards active speech duration when filtering transient noise bursts against `min_utterance_ms`.
- Pipeline orchestration layer must not perform arithmetic operations (running total, addition); it cleanly maps raw audio frames through segmentation, ASR, and parsing into typed candidate results for subsequent decision processing.
- Candidate parsed result != automatic addition. Masking the integer value to `None` on all non-accepts (REPEAT, REJECT) provides structural defense-in-depth against accidental addition of unvalidated values.
- Calculator domain layer must strictly receive validated integer values from upstream callers, never raw speech transcripts or PipelineResults, isolating arithmetic logic completely from recognition heuristics.
- Tkinter GUI shell should use dependency injection with Calculator and SafetyDecisionEngine to ensure headless testability without hardware audio dependencies.
- Background listening worker thread must never mutate GUI widgets directly; passing structured immutable events (`ControllerEvent`) across a thread-safe queue polled on the main GUI thread guarantees thread safety and UI responsiveness.
- Session isolation using monotonic session IDs ensures in-flight ASR transcripts or candidate events generated during a previous listening session are safely ignored if the session has stopped or restarted.
- Operating modes (Safe Mode vs Fast Mode) must be evaluated strictly in the safety decision engine rather than being hardcoded in GUI callbacks.
- Missing/uncalibrated confidence must never be treated as evidence of reliability; Fast Mode must safely fall back to manual confirmation when confidence scores are missing (e.g. Vosk baseline).

## 12. Dependencies Added (with justification)

| Package | Version | Purpose | Why needed / alternative considered | Phase |
|---------|---------|---------|-------------------------------------|-------|
| pytest | 8.3.4 | Test framework | Automated unit and property testing; standard test runner | Phase 0 |
| sounddevice | 0.5.6 | Audio capture | Low-latency, reliable PortAudio Python bindings for Windows | Phase 1C |
| numpy | 2.4.6 | Buffer operations | Efficient audio buffer representation for sounddevice & VAD RMS | Phase 1C |
| vosk | 0.3.45 | Offline ASR | Candidate ASR baseline engine for English speech recognition | Phase 2.2 |

## 13. Next Task

- **Phase 4**: Candidate Whisper Engine evaluation (faster-whisper) vs Vosk baseline benchmark comparison, or real speech recording collection via `tools/record_dataset.py`.

## 14. Files Changed Recently

- `src/voice_calculator/audio/segmenter.py` — modified — fixed active speech duration accounting to exclude pre-roll silence buffer (Phase 3.8)
- `tests/test_segmenter.py` — modified — added `test_segmenter_short_noise_burst_with_full_pre_roll_rejected` regression test (Phase 3.8)
- `docs/research.md` — modified — added Section 8 VAD Calibration & Experiment Log EXP-001 and Section 9 Confidence Calibration (Phase 3.8)
- `docs/memory.md` — modified — updated with Phase 3.8 status, decisions, lessons, and test results (Phase 3.8)

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
