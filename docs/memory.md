# Memory — Project Progress File

> **For the coding agent:** read this file FIRST every session; update it LAST every session (see `rules.md` §F). Keep it short: replace stale text, don't append forever. Never record anything here that was not actually done or measured.
> Other docs: `prd.md` (what), `architecture.md` (how), `phases.md` (order), `design.md` (UI), `research.md` (evidence), `rules.md` (constraints).

---

## 1. Project Status

- **Overall status:** Phase 1 (Deterministic English Number Parser) completed. All 170 unit and exhaustive tests passing.
- **Last updated:** 2026-10-01 by Antigravity

## 2. Current Phase

- Phase: **Phase 1 complete**; ready for **Phase 2 — ASR Interface and Prerecorded-Audio Baseline**.

## 3. Current Task

- Phase 1 completed. Next: Phase 2, subtask 2.1 (`asr/base.py`, `audio/wavio.py`, `FakeEngine`).

## 4. Completed Work

- Documentation pack created (`docs/prd.md`, `architecture.md`, `rules.md`, `phases.md`, `design.md`, `memory.md`, `research.md`).
- [0.1 Skeleton] Established virtual environment (Python 3.11.9), `.gitignore`, `pyproject.toml`, `requirements.txt`, `README.md`, package structure `src/voice_calculator/__init__.py`.
- [0.2 Config & logging] Implemented `config.py` constants and tunables, `logging_setup.py` with privacy-safe rotating file logging; added tests in `tests/test_config.py`, `tests/test_logging.py`, and `tests/test_smoke.py`.
- [1A Grammar Specification & Clarification] Defined formal grammar specification for 0–2000, unambiguous "and" / "a" rules, 1000–1999 structure, structural vs range error classification, normalization rules, reason codes, parser interface contract, and exhaustive testing plan.
- [1B Number Parser Implementation] Implemented `src/voice_calculator/numparse.py` with pure deterministic grammar parser, normalization, and reason code classification. Added `tests/test_numparse_cases.py` (documented accepted/rejected cases) and `tests/test_numparse_exhaustive.py` (exhaustive 0–2000 canonical words, 0–2000 digit strings, boundary values, invariants, and 500-iteration random fuzz testing).

## 5. Current Architecture (as implemented)

- Architecture foundation laid per `architecture.md`.
- Modules that exist in code: `voice_calculator.config`, `voice_calculator.logging_setup`, `voice_calculator.numparse`.
- Chosen ASR engine: **none yet** (baseline plan: Vosk + constrained grammar, pending Phase 3 ADR).
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

- Automated tests: **170 passed** (`pytest -v`).
- Last test command/result: `.\.venv\Scripts\pytest.exe -v` -> 170 passed in 0.46s (test_config: 4, test_logging: 3, test_numparse_cases: 156, test_numparse_exhaustive: 5, test_smoke: 2).
- Manual tests: None required for Phase 1.

## 10. Benchmark Status

- **No benchmarks run. No accuracy, latency, or resource numbers exist.** Dataset not yet recorded.
- See `research.md` for templates.

## 11. Important Lessons

- Normalization must check for hyphens adjacent to digits (`1-500`) to avoid converting non-canonical digit formats into valid tokens.
- Multi-number utterances containing multiple scale clauses (e.g. `one hundred two hundred`) must be detected and rejected as `MULTIPLE_NUMBERS`.

## 12. Dependencies Added (with justification)

| Package | Version | Purpose | Why needed / alternative considered | Phase |
|---------|---------|---------|-------------------------------------|-------|
| pytest | 8.3.4 | Test framework | Automated unit and property testing; standard test runner | Phase 0 |

## 13. Next Task

- **Phase 2, subtask 2.1 — Interface + WAV I/O** (`phases.md`): `ASREngine` protocol, `ASRResult`, `FakeEngine`, and `audio/wavio.py`.

## 14. Files Changed Recently

- `src/voice_calculator/numparse.py` — new — deterministic English number parser (Phase 1B)
- `tests/test_numparse_cases.py` — new — unit tests for accepted and rejected cases (Phase 1B)
- `tests/test_numparse_exhaustive.py` — new — exhaustive 0–2000, boundary, invariant, and fuzz tests (Phase 1B)
- `docs/memory.md` — modified — updated with Phase 1 completion and test results
- `docs/architecture.md` — modified — aligned §8 with formal grammar specification
- `docs/prd.md` — modified — formal grammar specification and unambiguous reason codes in §7
- `README.md` — modified — updated setup and testing instructions
- `src/voice_calculator/config.py` — new — configuration constants & tunables
- `src/voice_calculator/logging_setup.py` — new — privacy-safe logger setup

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
