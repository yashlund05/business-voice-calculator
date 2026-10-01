# Phases — Implementation Roadmap

> Doc role: **ORDER** of implementation. Requirements: `prd.md`. Design: `architecture.md`, `design.md`. Rules: `rules.md`. Track progress in `memory.md`; record experiments in `research.md`.
> Validation-first: the parser and the ASR evidence come **before** the audio loop and the GUI.
> Each phase is split into subtasks (e.g. `1.2`). **Give the coding agent ONE subtask per prompt.** Do not hand it a whole phase.

---

## How to Use This File (credit-efficient workflow)

1. Open `memory.md`; copy the "Next task" ID.
2. Send the agent the **Prompt Template** below with that subtask ID.
3. Review the Task Report (`rules.md` §H). Run the tests yourself if in doubt.
4. Commit is done by the agent (small commit). Move on only when the subtask's acceptance criteria are met.
5. At each **Phase Gate**, confirm exit criteria before starting the next phase.

### Prompt Template (copy, fill the brackets)

```
Follow docs/rules.md. Read docs/memory.md first.
Task: Phase [N], subtask [N.M] in docs/phases.md — "[title]".
Read only: [prd.md §X] [architecture.md §Y] [design.md §Z if UI].
Inspect existing code in [files/dirs] before editing; do not rewrite working modules.
Implement ONLY this subtask. Add/run tests. No new dependencies unless justified in memory.md.
Update docs/memory.md (and docs/research.md if you ran an experiment). Make one small Git commit.
Stop after this subtask and reply with the Task Report from rules.md §H.
```

Debug variant: `Follow docs/rules.md. Bug: [symptom + steps]. Write a failing regression test first, then fix with the smallest change, run tests, update memory.md, commit, report.`

### Phase Overview and Dependencies

| Phase | Name | Depends on | Needs user input? |
|-------|------|-----------|-------------------|
| 0 | Repository and environment foundation | — | confirm Python version |
| 1 | Strict deterministic number parser | 0 | no |
| 2 | ASR interface and prerecorded-audio baseline | 0, 1 | **record dataset (manual)** |
| 3 | ASR benchmark and architecture decision | 1, 2 | **review ADR + ratify provisional targets** |
| 4 | Microphone capture and continuous listening | 0, 3 (engine choice) | mic available |
| 5 | Validation and decision engine | 1, 3, 4 | no |
| 6 | Calculation core, history, undo, reset | 0 (logic is independent) | no |
| 7 | GUI integration | 4, 5, 6 | UI review |
| 8 | Reliability testing and Windows packaging | 7 | **real-use trial** |

---

## Phase 0 — Repository and Environment Foundation

**Objective:** a clean, reproducible repo where tests run.
**Prerequisites:** Python 3.11+ and Git installed on Windows.
**Dependencies on previous phases:** none.

| Subtask | Tasks | Files |
|---------|-------|-------|
| 0.1 Skeleton | Create the layout of `architecture.md` §4 with empty packages only; `.gitignore` (venv, `models/`, `data/`, `logs/`, `__pycache__`, `build/`, `dist/`, `*.wav` outside approved fixtures); `requirements.txt` (pytest only); `README.md` (setup + run tests, 10 lines); `pytest` config | `src/voice_calculator/__init__.py`, `tests/`, `.gitignore`, `requirements.txt`, `README.md` |
| 0.2 Config & logging | `config.py` with named constants (initially: sample rate, min/max value, queue size, poll interval); `logging_setup.py` privacy-safe defaults (`architecture.md` §13); 1–2 tests | `config.py`, `logging_setup.py`, `tests/test_config.py` |

**Tests:** `pytest` runs and passes (trivial tests OK). Verify `.gitignore` excludes `models/`, `data/`, `logs/`.
**Acceptance criteria:** fresh clone + venv + `pip install -r requirements.txt` + `pytest` passes; no model/data/log files tracked.
**Exit criteria / Stopping point:** first commit(s) made; `memory.md` updated (Python version recorded). **Stop.**

---

## Phase 1 — Strict Deterministic Number Parser

**Objective:** a pure `parse(text)` that accepts exactly the forms in `prd.md` §7 and rejects everything else with reason codes.
**Prerequisites:** Phase 0 done.
**Dependencies:** Phase 0.
**Read:** `prd.md` §7–8, `architecture.md` §8.

| Subtask | Tasks | Files |
|---------|-------|-------|
| 1.1 Test corpus first | Write tests from `prd.md` §7: accepted table, rejected table with expected reason codes, edge cases (hyphens, case, extra spaces, digit strings). Tests initially fail. | `tests/test_numparse_cases.py` |
| 1.2 Implementation | Implement normalization, closed vocabulary, grammar, range check, `ParseResult` + reason codes. Make 1.1 pass. | `numparse.py` |
| 1.3 Exhaustive & fuzz | Round-trip generator for all 0–2000 canonical word forms (generator lives in tests); fuzz test: random token sequences never yield a value unless they match the grammar; document any grammar gaps found (do not silently widen the grammar). | `tests/test_numparse_exhaustive.py` |

**Tests:** all three files pass.
**Acceptance criteria:** `prd.md` AC-1 met; parser never raises on arbitrary strings; no ML/LLM/network.
**Exit criteria:** tests pass; any ambiguity found is logged in `memory.md` "Pending decisions"; commit; **Stop.** (Phase Gate: user skims the accepted/rejected lists.)

---

## Phase 2 — ASR Interface and Prerecorded-Audio Baseline

**Objective:** run a baseline ASR over WAV files and print parsed results, without a microphone.
**Prerequisites:** Phase 1 done. Vosk small English model placed manually in `models/` (never committed).
**Dependencies:** Phases 0–1.
**Read:** `architecture.md` §7, `research.md` (dataset protocol).

| Subtask | Tasks | Files |
|---------|-------|-------|
| 2.1 Interface + WAV I/O | `ASREngine` protocol, `ASRResult`, a `FakeEngine` (returns scripted text) for tests; WAV read/write helpers (16 kHz mono int16) | `asr/base.py`, `audio/wavio.py`, tests |
| 2.2 Vosk baseline | `VoskEngine` with constrained number-word grammar; local model path from config; no auto-download; clear `ModelMissing` error; test with fake/skip marker when model absent | `asr/vosk_engine.py`, tests |
| 2.3 Dataset recording helper | `tools/record_dataset.py`: prompts the user with target numbers from a generated list, records one WAV per prompt to `data/recordings/`, writes `labels.csv`; includes a visible "recording" notice. **User then records the dataset following `research.md` protocol (manual).** | `tools/record_dataset.py` |
| 2.4 Transcribe CLI | `tools/transcribe.py <wav-or-dir>` → prints text, parsed value/rejection, elapsed ms per file | `tools/transcribe.py` |

**Tests:** unit tests with `FakeEngine`; ASR-dependent tests are skipped (not failed) when the model is missing.
**Acceptance criteria:** CLI processes a folder of WAVs offline and shows text + parse result + timing; no network use.
**Exit criteria:** user has recorded at least the calibration/dev set per `research.md` (or schedules it); baseline numbers are **not** claimed; `memory.md` updated; **Stop.**

---

## Phase 3 — ASR Benchmark and Architecture Decision

**Objective:** choose the ASR strategy using evidence. **This phase decides models; do not skip it.**
**Prerequisites:** labeled recordings exist (`research.md` §3) with dev/calibration/test separation.
**Dependencies:** Phases 1–2.
**Read:** `research.md` (metrics, templates), `architecture.md` §7, §16.

| Subtask | Tasks | Files |
|---------|-------|-------|
| 3.1 Benchmark harness | `tools/benchmark.py`: runs an engine over a labeled folder, outputs per-utterance CSV and the metrics in `research.md` §4 (Exact Integer Accuracy, False Addition Rate, etc.) computed with the **current default decision policy**; unit-test metric math with `FakeEngine` | `tools/benchmark.py`, tests |
| 3.2 Whisper candidate | Add `WhisperEngine` (faster-whisper, local model path, CPU int8, no auto-download); justify dependency in `memory.md`; test with skip marker | `asr/whisper_engine.py` |
| 3.3 Run benchmarks | Run Vosk-grammar and faster-whisper (`tiny.en`, `base.en`, optionally `small.en`) on the **dev/calibration** set; record latency and resource use; record results in `research.md` templates (real numbers only). Optional offline analysis: how often A and B agree/disagree, and whether disagreement predicts errors (hybrid hypothesis). | `research.md`, `data/results/` (git-ignored) |
| 3.4 Decision record | Write the ADR in `research.md`: chosen engine/model, rejected options, evidence, residual risks. Propose ratification of PROVISIONAL targets in `prd.md` §13. **Do not run the final test set yet.** | `research.md`, `memory.md` |

**Acceptance criteria:** results tables filled with measured values and dataset size N; ADR written; no fabricated numbers; the choice is justified by evidence even if "baseline is enough".
**Exit criteria / Phase Gate:** **user reviews and approves the ADR and the provisional targets.** Then **Stop.**

---

## Phase 4 — Microphone Capture and Continuous Listening

**Objective:** a headless (console) pipeline: mic → VAD → utterances → ASR → parse → printed result, running continuously and stopping cleanly.
**Prerequisites:** Phase 3 ADR approved (engine chosen).
**Dependencies:** Phases 0–3.
**Read:** `architecture.md` §3, §5, §6, §11.

| Subtask | Tasks | Files |
|---------|-------|-------|
| 4.1 Capture | `capture.py`: sounddevice stream, bounded queue, typed `MicNotFound`/`MicLost` errors; a fake audio source for tests (reads WAV) | `audio/capture.py`, tests |
| 4.2 VAD + segmenter | Energy-based VAD with hangover and pre-roll; segmenter emits utterances with stats (duration, peak, RMS, clipping, damaged); unit-test with synthetic signals and recorded WAVs; thresholds in `config.py` | `audio/vad.py`, `audio/segmenter.py`, tests |
| 4.3 Console pipeline | `tools/live_console.py`: worker thread wiring capture→segmenter→engine→parser; Start/Stop via keyboard in the console (dev tool only); clean shutdown; discards in-flight work on stop | `tools/live_console.py` |
| 4.4 VAD experiment (optional, only if 4.2 shows missed/clipped utterances) | Compare energy VAD vs Silero using `research.md` VAD template; adopt only with evidence and justified dependency | `audio/vad.py`, `research.md` |

**Tests:** segmenter/VAD tests offline; manual test: speak 20 numbers in a quiet room, note missed/clipped utterances in `research.md`.
**Acceptance criteria:** continuous listening for ≥ 10 minutes without crash or unbounded queue growth (measured, reported); Stop returns promptly; no GUI code involved.
**Exit criteria:** `memory.md` updated with observed issues; **Stop.**

---

## Phase 5 — Validation and Decision Engine

**Objective:** deterministic ACCEPT/CONFIRM/REJECT policy, safe by default.
**Prerequisites:** Phases 1, 3, 4.
**Dependencies:** 1, 3, 4.
**Read:** `architecture.md` §9, `prd.md` §8, `research.md` (confidence calibration).

| Subtask | Tasks | Files |
|---------|-------|-------|
| 5.1 Decision core | `decision.py` pure function with hard rules and `auto_accept_enabled=false` default (confirm-all for parsed values; REJECT for failures; zero → CONFIRM); tests for every hard rule, including AC-3 and AC-10 | `decision.py`, tests |
| 5.2 Signal checks | Add utterance-quality rejects (too short/long/quiet/clipped/damaged) using config thresholds; tests with synthetic stats | `decision.py`, `config.py`, tests |
| 5.3 Calibration run | Using the **calibration set only**, evaluate candidate auto-accept rules via `tools/benchmark.py` (add a `--policy` option); record in `research.md` calibration record | `tools/benchmark.py`, `research.md` |
| 5.4 Adopt or keep safe default | If a rule achieves 0 false additions on calibration data with acceptable confirm rate, add it **behind a config flag** and document; otherwise keep confirm-all and record why | `decision.py`, `memory.md` |

**Acceptance criteria:** AC-3, AC-10 tests pass; any enabled auto-accept rule is backed by recorded calibration evidence; thresholds not tuned on the final test set.
**Exit criteria:** **Stop.** (Phase Gate: user approves whether auto-accept stays off or on.)

---

## Phase 6 — Calculation Core, History, Undo, Reset

**Objective:** pure, fully tested logic for total, history, undo, reset, plus the state machine and a headless controller.
**Prerequisites:** Phase 0 (may be done earlier if convenient).
**Dependencies:** Phase 0.
**Read:** `architecture.md` §6, §10, `prd.md` FR-9–FR-11.

| Subtask | Tasks | Files |
|---------|-------|-------|
| 6.1 Calculator | `Calculator`: add, undo (repeatable), reset, derived total, display log of non-added events; range enforcement; property-style tests (total == sum of non-undone entries) | `calculator.py`, tests |
| 6.2 State machine | `state.py` enum + transition table from `architecture.md` §6; invalid transitions ignored without exceptions; tests for every row | `state.py`, tests |
| 6.3 Headless controller | `controller.py`: consumes pipeline events/decisions, applies to calculator/state; testable with fakes; no Tk | `controller.py`, tests |

**Acceptance criteria:** AC-2; every state-table row tested; no GUI/audio imports in these modules.
**Exit criteria:** **Stop.**

---

## Phase 7 — GUI Integration

**Objective:** the Tkinter app exactly per `design.md`, wired to the real pipeline.
**Prerequisites:** Phases 4, 5, 6.
**Dependencies:** 4, 5, 6.
**Read:** `design.md` (all), `architecture.md` §11.

| Subtask | Tasks | Files |
|---------|-------|-------|
| 7.1 Static layout | Window with all widgets from `design.md` §12, messages table, no logic | `gui/app.py`, `gui/messages.py` |
| 7.2 Wiring with fake pipeline | Controller events drive status/total/history using a scripted fake pipeline; `after()` polling; Start/Stop/Undo/Reset/Add/Discard handlers | `gui/app.py`, `controller.py` |
| 7.3 Real pipeline | Replace fake with real capture→ASR pipeline in worker thread; model loading in background; Start disabled until ready | `controller.py`, `gui/app.py` |
| 7.4 Confirmation, undo, reset flows | Confirmation panel + keyboard shortcuts; undo; reset dialog (Cancel default); exactly per `design.md` §6, §8, §9 | `gui/app.py` |
| 7.5 Error states | All messages from `design.md` §7; error recovery paths from `prd.md` §9 | `gui/app.py`, `gui/messages.py` |

**Tests:** controller tests with fakes (automated); GUI checked by a manual checklist (record in `memory.md`); simple smoke test that the window builds and closes.
**Acceptance criteria:** FR-1…FR-15 manually verified; no Tk calls off the main thread; AC-7 method defined.
**Exit criteria:** **Stop.** (Phase Gate: user tries the app and lists UI issues.)

---

## Phase 8 — Reliability Testing and Windows Packaging

**Objective:** prove it is reliable, then package.
**Prerequisites:** Phase 7.
**Dependencies:** all earlier phases.
**Read:** `prd.md` §13, `research.md` §4 and §13, `architecture.md` §14.

| Subtask | Tasks | Files |
|---------|-------|-------|
| 8.1 Latency & stall measurement | Instrument timing (debug only); measure end-of-speech → UI latency and GUI stalls; record in `research.md` | `tools/`, `research.md` |
| 8.2 Long-session soak | 60-minute continuous run; record memory/CPU trend and crashes | `research.md` |
| 8.3 Error matrix | Manually trigger each error in `prd.md` §9; record pass/fail | `memory.md` |
| 8.4 Final test-set evaluation | Run the **held-out test set once** with the final configuration; report AC-4, AC-5, AC-6 with N and upper bounds. Any failure → return to Phase 5 (do not tune on this set; collect a new test set if needed) | `research.md` |
| 8.5 Packaging | PyInstaller one-folder build; models placed in app folder; build instructions in `README.md`; `build/`, `dist/` git-ignored | build spec, `README.md` |
| 8.6 Clean-machine smoke test | Run packaged build offline on a machine/profile without Python; check AC-9, AC-12 | `memory.md` |

**Acceptance criteria:** `prd.md` AC-4…AC-12 measured and recorded (met or explicitly reported as not met).
**Exit criteria:** user performs a real-use trial with the father's workflow; issues logged in `memory.md`. **Stop.** MVP complete only when the user says so.
