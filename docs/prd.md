# PRD — Voice Calculator

> Doc role: defines **WHAT** the product must do. How it works: `architecture.md`. Coding constraints: `rules.md`. Order of work: `phases.md`. UI behavior: `design.md`. Actual progress: `memory.md`. Evidence: `research.md`.
> Status labels used in all docs: **FIXED** (requirement, do not change without a documented reason), **DEFAULT** (sensible starting choice, may change), **PROVISIONAL** (numeric target pending benchmark/user approval), **OPEN** (decision deferred).

---

## 1. Product Summary

A Windows desktop application that listens (offline) to spoken English numbers from 0 to 2000, one number at a time, and adds each to a large, always-visible running total. Listening starts and stops only via physical GUI buttons. There are no voice commands.

## 2. Problem Statement

The user's father repeatedly adds numbers on a physical calculator for his business. Hands and eyes are busy; speaking numbers would be faster. **A wrong total is worse than a slow one**, so the product prioritizes correctness over convenience: when unsure, it asks; it never silently adds a doubtful value.

## 3. Intended User and Environment

- **User:** a non-technical adult who does repetitive addition. Needs large text, few buttons, plain-language messages.
- **Hardware:** Windows laptop (Windows 10/11), built-in or simple headset microphone. CPU only (no GPU assumed).
- **Environment:** quiet room (**FIXED** for MVP). Noisy shops, background speech, and multiple speakers are out of scope.
- **Speaker:** one speaker, English. Accent coverage is measured, not assumed (see `research.md`).
- **Speaking style (DEFAULT):** one number per utterance, short pause (about 0.7 s, tunable) between numbers.

## 4. Goals and Non-Goals

### Goals
1. Correct running total above all else.
2. Hands-free number entry via continuous listening while activated.
3. Clear status at all times (listening, processing, confirm, error).
4. Fully offline and private.
5. Simple correction: undo, discard, reset.

### Non-Goals (MVP)
- Subtraction, multiplication, division, percentages, decimals, negative numbers.
- Voice commands of any kind (including "undo", "stop", "yes", "no", "clear", "total").
- Numbers above 2000 or below 0 in a single utterance.
- Multiple numbers in a single utterance.
- Other languages, multiple speakers, noisy environments.
- Cloud APIs, accounts, telemetry, auto-update.
- Using an LLM for parsing or arithmetic.
- Persisting sessions across restarts, exporting, printing.
- macOS/Linux support.

## 5. Functional Requirements

| ID | Requirement |
|----|-------------|
| FR-1 | **Start** button begins continuous listening. **Stop** button ends it. These are the only ways to change listening state. (**FIXED**) |
| FR-2 | While listening, the app segments speech into utterances, recognizes each locally, parses it, validates it, and decides ACCEPT / CONFIRM / REJECT (see `architecture.md` §9). |
| FR-3 | ACCEPT adds the integer to the total and shows it as "Added". CONFIRM shows the interpreted number and requires a physical action (button or key) before adding. REJECT adds nothing and prompts the user to repeat. |
| FR-4 | Parsing is a strict deterministic English number-word parser for 0–2000 (§7). No guessing. |
| FR-5 | Arithmetic is exact integer addition by a deterministic calculation core. |
| FR-6 | Large running total is always visible. |
| FR-7 | Show current status: Idle, Starting, Listening, Hearing speech, Processing, Needs confirmation, Error. |
| FR-8 | Show last recognized number and a scrollable list of recent entries (value, outcome; at least the last 20 visible). |
| FR-9 | **Undo** removes the most recent added entry and subtracts it from the total. Repeatable until history is empty. |
| FR-10 | **Discard** (during confirmation) drops the pending value without adding. |
| FR-11 | **Reset** clears total and history only after an explicit confirmation dialog. |
| FR-12 | Microphone and recognition failures show plain-language messages and a recovery action (§9). |
| FR-13 | No voice command recognition: spoken words other than number words are rejected, never interpreted as actions. (**FIXED**) |
| FR-14 | All audio and recognized values are processed locally; no network calls in normal operation. (**FIXED**) |
| FR-15 | Application remains responsive (GUI never blocked by capture, VAD, or recognition). |

## 6. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-1 | **Correctness first.** Wrong additions must be minimized by design (decision engine), measured, and reported. |
| NFR-2 | **Offline.** Works with network disabled. Models are bundled or placed locally; none downloaded at runtime. |
| NFR-3 | **Responsiveness (PROVISIONAL).** GUI event loop never blocked more than 100 ms. End-of-speech to on-screen result p95 ≤ 1.5 s, worst case ≤ 3 s on target laptop. |
| NFR-4 | **Stability (PROVISIONAL).** 60-minute continuous listening session with no crash and no unbounded memory growth (measured and reported). |
| NFR-5 | **Resource use.** CPU-only; no GPU required. Idle (not listening) CPU use is near zero. Numeric limits recorded in `research.md`. |
| NFR-6 | **Determinism.** Same text input always yields same parse result and same arithmetic. |
| NFR-7 | **Maintainability.** Modular but small; justified dependencies; automated tests. |
| NFR-8 | **Packaging.** Windows packaging only after the core app is validated (Phase 8). |

## 7. Supported Spoken Number Formats

The parser input is normalized lowercase text (hyphens treated as spaces). Output is an integer 0–2000 or a rejection with a reason code.

### Accepted (MVP)

| Spoken | Value | Notes |
|--------|-------|-------|
| zero | 0 | "oh", "nought", "nil" not accepted (OPEN, default reject) |
| one … nineteen | 1–19 | |
| twenty, thirty, … ninety | 20–90 | |
| forty-five / forty five | 45 | tens + units; units must be 1–9 |
| one hundred / a hundred | 100 | |
| one hundred and fifty / one hundred fifty | 150 | "and" optional, only after "hundred" |
| two hundred fifty / two hundred and fifty | 250 | hundreds digit 1–9 |
| two hundred and five | 205 | |
| nine hundred ninety-nine | 999 | |
| one thousand / a thousand | 1000 | |
| one thousand five hundred / one thousand and fifty | 1500 / 1050 | thousand + optional "and" + 1–999 form |
| one thousand nine hundred ninety-nine | 1999 | |
| fifteen hundred | 1500 | "teen + hundred" for 11–19 only (1100–1900) |
| fifteen hundred and fifty | 1550 | DEFAULT accept; remainder 1–99 after "N hundred" where N in 11–19 |
| two thousand | 2000 | exactly 2000 only |
| Digit-only ASR output such as `45`, `1500` | same | Accepted only as a plain integer string 0–2000 with no separators, signs, decimals, or leading zeros (except `0`) |

### Rejected (never guessed)

| Input | Reason code | Why |
|-------|-------------|-----|
| (empty), "um", any non-number word | `NOT_A_NUMBER` | Includes command-like words ("undo", "stop", "yes") |
| two thousand and one, two thousand five hundred, twenty five hundred, 2001 | `OUT_OF_RANGE` | Above 2000 |
| minus five, negative ten | `UNSUPPORTED` | Negatives not supported |
| three point five | `UNSUPPORTED` | Decimals not supported |
| hundred (alone), hundred fifty | `MALFORMED` | Needs a multiplier ("one hundred" or "a hundred") |
| one two three, four five | `MULTIPLE_NUMBERS` / `AMBIGUOUS` | Digit-by-digit sequences are ambiguous |
| twenty twenty, fifteen fifty, thirteen fifty | `AMBIGUOUS` | Year-style/compound readings are not allowed |
| twenty ten, forty fifty, five five | `MALFORMED` | Invalid structure |
| fifty hundred, twenty hundred, ten hundred | `OUT_OF_RANGE` / `MALFORMED` | Only 11–19 hundred permitted |
| one hundred hundred, thousand thousand | `MALFORMED` | Repeated scale words |
| hundred and, and fifty | `MALFORMED` | Dangling "and" |
| forty and five | `MALFORMED` | "and" only valid after hundred/thousand |
| 007, 1,500, 15.0, ٤٥ | `MALFORMED` | Non-canonical digit forms |
| Two valid numbers in one utterance ("forty five fifty") | `MULTIPLE_NUMBERS` or `AMBIGUOUS` | One number per utterance in MVP (OPEN: may revisit) |

The full accepted/rejected corpus becomes the parser test suite (Phase 1). Anything not listed as accepted is rejected.

### Special case
- **Zero (DEFAULT):** a parsed `0` always requires CONFIRM (commonly produced by silence/noise misrecognition). May be revisited after benchmark.

## 8. Rejected and Ambiguous Input Behavior

- **REJECT:** nothing is added. UI shows "Didn't catch that — please say the number again." plus (optionally) what was heard in small text (debug-friendly, not alarming).
- **CONFIRM:** UI shows the interpreted number large, e.g. "Did you say 150?" with **Add** and **Discard** buttons (and keyboard shortcuts). Nothing is added until the user acts.
- Rejections and discards never change the total and are recorded in history as non-added events (visually distinct).
- Utterances too short, too long, clipped, or too quiet: REJECT with specific message (see `design.md` §7).
- Repeated rejections do not escalate into voice commands or alternate input modes.

## 9. Error Handling Requirements

| Situation | Required behavior |
|-----------|-------------------|
| No microphone found | Status = Error. Message: "No microphone found. Plug in or enable a microphone, then press Start." Start remains available. |
| Microphone in use / permission denied | Plain message pointing to Windows microphone privacy settings. |
| Microphone disconnected during listening | Stop listening safely, keep total and history, show message, allow Start again. |
| Model files missing or failed to load | Message naming the missing component by plain name; app stays usable for Undo/Reset; Start disabled. |
| Recognition exception | Skip that utterance, show "Couldn't process that — please repeat", keep listening. Repeated failures (DEFAULT: 5 consecutive) stop listening with an error message. |
| Unexpected internal error | Never corrupt the total; show generic error; log locally (no audio, no values unless debug logging enabled). |
| Any error | Total and history remain intact and visible. |

## 10. Privacy Requirements (**FIXED** unless noted)

- Audio never leaves the machine; no network calls in normal operation; no telemetry.
- Raw audio is **not** saved by default. Optional debug/benchmark recording must be explicit, visibly indicated, stored under a git-ignored local folder.
- Logs contain events and error types; recognized numeric values and transcripts only in explicit debug mode. Logs stay local and git-ignored.
- No model files, recordings, logs, or virtual environments committed to Git.
- Business data (totals, entries) is in memory only in MVP.

## 11. MVP Scope

In scope: Start/Stop; continuous listening; one ASR baseline (see `architecture.md` §7); strict parser; decision engine (ACCEPT/CONFIRM/REJECT); calculation core with history/undo/reset; Tkinter GUI per `design.md`; local logging; tests; benchmark tooling; Windows packaging after validation.

Not in scope: everything in Non-Goals and Future Enhancements.

## 12. Future Enhancements (NOT MVP; do not implement)

- Hybrid/second-pass ASR (only if benchmark justifies).
- Fine-tuning or custom-vocabulary models.
- Session autosave/crash recovery, export (CSV/text), printable tape.
- Manual keyboard number entry and entry editing.
- Multiple numbers per utterance; larger ranges; decimals/currency.
- Subtraction or other operators (would require a new PRD revision).
- Noisy-environment support, push-to-talk hardware, speaker adaptation.
- Installer, auto-update, other languages.

## 13. Measurable Acceptance Criteria

Targets marked **PROVISIONAL** are initial proposals; they must be reviewed and ratified by the user in the Phase 3 ADR (`research.md`). Never claim a target is met without a recorded measurement.

| ID | Criterion | Measure |
|----|-----------|---------|
| AC-1 | Parser correctness | 100% of parser corpus passes: every integer 0–2000 round-trips from canonical word forms; all accepted variants in §7; all rejection cases in §7. |
| AC-2 | Arithmetic correctness | Calculation/undo/reset property-style tests pass; total always equals sum of non-undone accepted entries. |
| AC-3 | No silent doubtful additions | Decision engine tests prove: parse failure → REJECT; zero → CONFIRM; any rule-flagged uncertainty → CONFIRM/REJECT, never ACCEPT. |
| AC-4 | False Addition Rate (PROVISIONAL) | **0** wrong values added without user confirmation on a held-out test set of **≥ 500** utterances (target speaker, quiet room). Report N and the 95% upper bound (≈ 3/N when 0 errors). A non-zero result fails AC-4 and triggers redesign of thresholds/policy. |
| AC-5 | Usability (PROVISIONAL) | Combined CONFIRM + REJECT rate on valid in-range test utterances ≤ 20%. If exceeded, report it and the trade-off; do not relax AC-4 to compensate. |
| AC-6 | Latency (PROVISIONAL) | End-of-speech to UI result: p95 ≤ 1.5 s, max ≤ 3 s on target laptop. |
| AC-7 | Responsiveness | No GUI event-loop stall > 100 ms during listening/recognition (measured). |
| AC-8 | Stability (PROVISIONAL) | 60-minute continuous session: no crash; memory growth reported and ≤ 50 MB. |
| AC-9 | Offline | App runs with network disabled; no outbound connection attempts observed. |
| AC-10 | No voice commands | Test: non-number words (incl. "undo", "stop", "yes") produce REJECT and no state change. |
| AC-11 | Error recovery | Each error in §9 is triggered in manual testing; total/history preserved. |
| AC-12 | Packaging | Packaged Windows build passes AC-6/AC-9 smoke checks on a clean machine/profile. |
