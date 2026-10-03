# Phases — Implementation Roadmap

> Doc role: **ORDER** of implementation. Requirements: `prd.md`. Design: `architecture.md`, `design.md`. Rules: `rules.md`. Track progress in `memory.md`; record experiments in `research.md`.
> Validation-first: the parser and the ASR evidence come **before** the audio loop and the GUI.
> Each phase is split into subtasks (e.g. `5A`). **Give the coding agent ONE subtask per prompt.** Do not hand it a whole phase.

---

## How to Use This File (credit-efficient workflow)

1. Open `memory.md`; copy the "Next task" ID.
2. Send the agent the **Prompt Template** below with that subtask ID.
3. Review the Task Report (`rules.md` §H). Run the tests yourself if in doubt.
4. Commit is done by the agent (small commit). Move on only when the subtask's acceptance criteria are met.
5. At each **Phase Gate**, confirm exit criteria before starting the next phase.

### Prompt Template (copy, fill the brackets)

```text
Follow docs/rules.md. Read docs/memory.md first.
Task: Phase [N], subtask [N.M] in docs/phases.md — "[title]".
Read only: [prd.md §X] [architecture.md §Y] [design.md §Z if UI].
Inspect existing code in [files/dirs] before editing; do not rewrite working modules.
Implement ONLY this subtask. Add/run tests. No new dependencies unless justified in memory.md.
Update docs/memory.md (and docs/research.md if you ran an experiment). Make one small Git commit.
Stop after this subtask and reply with the Task Report from rules.md §H.
```

Debug variant: `Follow docs/rules.md. Bug: [symptom + steps]. Write a failing regression test first, then fix with the smallest change, run tests, update memory.md, commit, report.`

---

### Phase Overview and Status

| Phase | Name | Scope / Summary | Status |
|---|---|---|---|
| **0** | Repository & Environment Foundation | Project layout, config constants, privacy-safe logging, testing harness | **COMPLETED** |
| **1** | Strict Deterministic Number Parser | 0–2000 formal grammar, normalization, reason codes, exhaustive/fuzz tests | **COMPLETED** |
| **2** | ASR Interface & Prerecorded Audio Baseline | ASREngine protocol, WAV I/O, Vosk baseline, benchmark CLI, transcribe tool | **COMPLETED** |
| **3** | Full Desktop Architecture Foundation | EnergyVAD, segmenter, pipeline orchestrator, safety decision engine, calculator core, Tkinter GUI, controller, Safe/Fast modes | **COMPLETED** |
| **4** | Candidate ASR Evaluation & Real Phone Benchmark | 4A FasterWhisperEngine, 4B low-end CPU benchmark on Dad dataset, 4C natural parser expansion + re-benchmark, 4D safety audit, 4E cancelled | **COMPLETED** |
| **5** | Validation, Error Audit & Safety Calibration | 5A error audit & synthetic stress, 5B confirmation/recovery reliability, 5C ASR ADR (P2) + target ratification (P5), 5D VAD (P3) + auto-accept (P4), 5E multi-number (P7) + zero rule (P8) | **COMPLETED** |
| **6** | Reliability Testing, Packaging & Trial | Long-session soak, error matrix, PyInstaller one-folder packaging (P9), real-world trial | **PLANNED** |

---

## Phase 0 — Repository and Environment Foundation (COMPLETED)

**Objective:** Clean, reproducible repository where tests run and offline development standards are enforced.

| Subtask | Tasks | Files | Status |
|---|---|---|---|
| 0.1 Skeleton | Directory layout, `.gitignore` (venv, models, data, logs), `requirements.txt`, `README.md`, pytest config | `src/voice_calculator/__init__.py`, `tests/`, `.gitignore` | **DONE** |
| 0.2 Config & logging | `config.py` constants, `logging_setup.py` privacy-safe rotating file logging, initial unit tests | `config.py`, `logging_setup.py`, `tests/test_config.py` | **DONE** |

---

## Phase 1 — Strict Deterministic Number Parser (COMPLETED)

**Objective:** Pure deterministic `parse(text)` for 0–2000 with explicit rejection reason codes and zero ML/LLM dependencies.

| Subtask | Tasks | Files | Status |
|---|---|---|---|
| 1.1 Test corpus | Acceptance and rejection test suites from formal grammar specification | `tests/test_numparse_cases.py` | **DONE** |
| 1.2 Implementation | Text normalization, closed vocabulary, grammar parsing, range enforcement, `ParseResult` dataclass | `src/voice_calculator/numparse.py` | **DONE** |
| 1.3 Exhaustive & fuzz | 0–2000 canonical words round-trip generator, digit string verification, randomized token fuzzing | `tests/test_numparse_exhaustive.py` | **DONE** |

---

## Phase 2 — ASR Interface and Prerecorded-Audio Baseline (COMPLETED)

**Objective:** Offline baseline ASR execution over 16 kHz mono WAV files with deterministic outcome classification.

| Subtask | Tasks | Files | Status |
|---|---|---|---|
| 2.1 Interface + WAV I/O | `ASREngine` protocol, `ASRResult`, `FakeEngine`, strict 16 kHz mono int16 WAV reader/writer | `src/voice_calculator/asr/base.py`, `audio/wavio.py` | **DONE** |
| 2.2 Vosk baseline | `VoskEngine` with constrained number grammar, local model path configuration, offline error handling | `src/voice_calculator/asr/vosk_engine.py` | **DONE** |
| 2.3 Dataset recording helper | `tools/record_dataset.py` with 94 structured prompt items, category filtering, interactive recording | `tools/record_dataset.py` | **DONE** |
| 2.4 Transcribe CLI & Benchmark harness | `tools/transcribe.py` CLI and `tools/benchmark.py` harness with outcome classification | `tools/transcribe.py`, `tools/benchmark.py` | **DONE** |

---

## Phase 3 — Full Desktop Architecture Foundation (COMPLETED)

**Objective:** Complete modular desktop application architecture from audio capture to Tkinter UI.

| Subtask | Tasks | Files | Status |
|---|---|---|---|
| 3.1 Prompt Consistency | Automated validation ensuring all dataset prompts conform to parser grammar | `tests/test_benchmark.py` | **DONE** |
| 3.2 VAD & Segmentation | `EnergyVAD` detector and `UtteranceSegmenter` online FSM with pre-roll and hangover | `src/voice_calculator/audio/vad.py`, `segmenter.py` | **DONE** |
| 3.3 Audio Pipeline | `AudioPipeline` orchestrating capture $\rightarrow$ segmentation $\rightarrow$ ASR $\rightarrow$ parsing | `src/voice_calculator/pipeline.py` | **DONE** |
| 3.4 Safety Decision Engine | `SafetyDecisionEngine` classifying pipeline results into ACCEPT, REPEAT, REJECT; value masking | `src/voice_calculator/decision.py` | **DONE** |
| 3.5 Calculator Core | `Calculator` state, immutable `HistoryEntry`, reversible LIFO `undo()`, reset dialog logic | `src/voice_calculator/calculator.py` | **DONE** |
| 3.6 Desktop GUI & Controller | `VoiceCalculatorApp` Tkinter UI and `ListeningController` background worker thread with session isolation | `src/voice_calculator/gui.py`, `controller.py` | **DONE** |
| 3.7 Safe & Fast Modes | `OperatingMode` (SAFE, FAST) selector with strict uncalibrated confidence gating | `src/voice_calculator/decision.py`, `gui.py` | **DONE** |
| 3.8 VAD Pre-Roll Bug Fix | Fixed pre-roll silence buffer accounting in `UtteranceSegmenter` speech duration calculation | `src/voice_calculator/audio/segmenter.py` | **DONE** |

---

## Phase 4 — Candidate ASR Evaluation & Real Phone Benchmark (COMPLETED)

**Objective:** Low-end-first comparative ASR evaluation on real recorded speech and parser safety audit.

| Subtask | Tasks | Files | Status |
|---|---|---|---|
| 4A Whisper Candidate | Integrated `FasterWhisperEngine` (CTranslate2 `int8` CPU fallback, GPU optional, uncalibrated score invariant) | `src/voice_calculator/asr/whisper_engine.py` | **DONE** |
| 4B Low-End CPU Benchmark | Dual-engine benchmark on 61-sample Dad dataset (`data/processed_phone/benchmark_dad/`). Vosk EIA 47.54%, tiny.en EIA 62.30% (tiny.en 60% higher wrong values: 13.11% vs 8.20%) | `data/processed_phone/analysis/`, `analysis/results/` | **DONE** |
| 4C Natural Parser Expansion | Deterministic parser expansion for natural bare `hundred` and `thousand` forms. Vosk EIA rose from 47.54% $\rightarrow$ 57.38%, rejections dropped from 44.26% $\rightarrow$ 31.15% | `src/voice_calculator/numparse.py`, `tests/` | **DONE** |
| 4D Parser Safety Audit | Prompt-by-prompt safety regression audit across all 61 samples. Proved 7 wrong values are ASR acoustic omissions, safely contained by confirm-by-default architecture | `docs/research.md` (EXP-003) | **DONE** |
| 4E Natural-Speed Recording | New natural-speed recording session | *CANCELLED (user's father has no time; proceed with existing 61-sample baseline dataset)* | **CANCELLED** |

---

## Phase 5 — Validation, Error Audit & Safety Calibration (IN PROGRESS)

**Objective:** Thorough safety hardening, error auditing, confirmation reliability, and evidence-based ADR ratification without requiring new live recordings.

| Subtask | Tasks | Files | Status |
|---|---|---|---|
| **5A Error Audit & Synthetic Stress** | Audit error patterns on existing 61-sample Dad dataset; generate synthetic acoustic perturbations (noise floor, gain shifts, truncated pauses) to measure VAD and ASR robustness | `tools/`, `docs/research.md` | **READY** |
| **5B Confirmation & Recovery Reliability** | Comprehensive invariant testing of GUI confirmation, Discard, Undo stack reversibility, and plain-language error messaging under abnormal pipeline events | `tests/test_decision.py`, `tests/test_gui.py`, `tests/test_controller.py` | **DONE** |
| **5C ASR Model ADR (P2)** | Formalize Architecture Decision Record (ADR-001) in `docs/research.md` comparing Vosk baseline vs faster-whisper on low-end CPU hardware constraints | `docs/research.md`, `docs/memory.md` | **DONE** (ADR-001 + ADR-004 accepted) |
| **5D VAD Calibration (P3) & Auto-Accept Rules (P4)** | Evaluate VAD hangover/threshold trade-offs on existing dataset; analyze confidence distributions to determine if any auto-accept rule can achieve 0 false additions | `src/voice_calculator/audio/vad.py`, `decision.py`, `docs/research.md` | **DONE** (ADR-002 + ADR-003 accepted; defaults retained per evidence) |
| **5E Multi-Number (P7) & Zero Rule (P8)** | Verify multi-number rejection hardening (`RejectReason.MULTIPLE_NUMBERS`) and enforce zero confirmation rule (`zero` always requires confirmation) | `src/voice_calculator/numparse.py`, `decision.py`, tests | **DONE** (P7/P8 verified & resolved; no src changes needed) |

---

## Phase 6 — Reliability Testing, Packaging & Trial (PLANNED)

**Objective:** Long-session stability verification, standalone Windows packaging, and user acceptance trial.

| Subtask | Tasks | Files | Status |
|---|---|---|---|
| 6.1 Long-Session Soak | 60-minute continuous listening soak test verifying bounded memory RSS, CPU stability, and zero GUI event stalls | `tools/`, `docs/research.md` | **DONE** (EXP-008: AC-8 PASS; AC-7 re-verify in foreground at 6.4) |
| 6.2 Error Matrix Verification | Trigger and verify recovery from all error conditions in `prd.md` §9 (mic disconnect, malformed speech, model missing) | `tests/`, `docs/memory.md` | **DONE** (7/7 conditions verified; 3 spec gaps fixed; AC-11; hardware variants deferred to 6.4) |
| 6.3 Windows Packaging (P9) | PyInstaller one-folder packaging build spec bundling models and offline runtime | `build_spec/`, `README.md` | **DONE** (ADR-005 one-folder; 8/8 verification checks PASS; 2 packaging defects fixed) |
| 6.4 Clean-Machine Trial | Verify packaged build on a clean Windows machine without Python; conduct user/father workflow trial | `docs/memory.md` | **PLANNED** |
