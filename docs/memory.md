# Memory — Project Progress File

> **For the coding agent:** read this file FIRST every session; update it LAST every session (see `rules.md` §F). Keep it short: replace stale text, don't append forever. Never record anything here that was not actually done or measured.
> Other docs: `prd.md` (what), `architecture.md` (how), `phases.md` (order), `design.md` (UI), `research.md` (evidence), `rules.md` (constraints).

---

## 1. Project Status

- **Overall status:** NOT YET IMPLEMENTED (documentation only).
- **Last updated:** (date) by (agent/user)

## 2. Current Phase

- Phase: **0 — Repository and environment foundation** (not started)

## 3. Current Task

- None in progress.

## 4. Completed Work

- Documentation pack created (`docs/prd.md`, `architecture.md`, `rules.md`, `phases.md`, `design.md`, `memory.md`, `research.md`).
- (No code, tests, or experiments completed yet.)

_Template for new entries:_ `- [Phase.Subtask] <what was done> — commit <hash>`

## 5. Current Architecture (as implemented)

- Not implemented. Intended architecture: `architecture.md`.
- Modules that exist in code: _none_.
- Chosen ASR engine: **none yet** (baseline plan: Vosk + constrained grammar, pending Phase 3 ADR).
- VAD: **none yet** (plan: energy baseline).
- Auto-accept policy: **off** (confirm-all) by default.

## 6. Confirmed Decisions

| # | Decision | Date | Source/Reason |
|---|----------|------|---------------|
| 1 | Windows desktop, Python, offline, English, 0–2000, addition only, buttons only, no voice commands | — | `prd.md` (FIXED requirements) |
| 2 | Parser and arithmetic are deterministic; no LLM | — | `rules.md` §C |
| 3 | Uncertain recognition is never silently added; default policy is confirm-all until calibrated | — | `architecture.md` §9 |
| 4 | Tkinter GUI; worker thread + queue model | — | `architecture.md` §11 |

## 7. Pending Decisions

| # | Question | Default for now | Resolve in |
|---|----------|-----------------|-----------|
| P1 | Python version | 3.11+ | Phase 0 |
| P2 | ASR engine/model (Vosk, faster-whisper size, hybrid) | Vosk + grammar baseline | Phase 3 ADR |
| P3 | VAD choice and timings | energy VAD | Phase 4 |
| P4 | Auto-accept rules/thresholds | none (confirm-all) | Phase 5 |
| P5 | Ratify PROVISIONAL targets in `prd.md` §13 | as written | Phase 3 gate |
| P6 | Accept "fifteen hundred and fifty"-style forms | accept | Phase 1 |
| P7 | Multiple numbers per utterance | reject | Post-MVP |
| P8 | Zero requires confirm | yes | after benchmark |
| P9 | PyInstaller one-folder vs one-file | one-folder | Phase 8 |

## 8. Known Bugs

- None recorded.

_Template:_ `- [ID] <symptom> — steps — status — regression test: <name or "pending">`

## 9. Test Status

- Automated tests: **not run — none exist yet.**
- Last test command/result: _n/a_
- Manual tests: _none done_

## 10. Benchmark Status

- **No benchmarks run. No accuracy, latency, or resource numbers exist.** Dataset not yet recorded.
- See `research.md` for templates.

## 11. Important Lessons

- (none yet)

_Template:_ `- <lesson> (Phase.Subtask)`

## 12. Dependencies Added (with justification)

| Package | Version | Purpose | Why needed / alternative considered | Phase |
|---------|---------|---------|-------------------------------------|-------|
| _none yet_ | | | | |

## 13. Next Task

- **Phase 0, subtask 0.1 — Skeleton** (`phases.md`).

## 14. Files Changed Recently

- `docs/*.md` (initial creation)

_Update with: `path — new/modified — one-line reason` (keep last ~10 entries)._

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

- [ ] Status/phase/task updated
- [ ] Completed work and files changed listed
- [ ] Test status reflects what was *actually run*
- [ ] New decisions, bugs, dependencies, lessons recorded
- [ ] Next task set (one subtask)
