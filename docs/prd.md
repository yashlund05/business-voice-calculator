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

The parser input is normalized text. Output is an integer 0–2000 or a rejection with an explicit reason code.

### 7.1 Formal Number Grammar (0–2000)

The accepted linguistic grammar consists of deterministic English numerical forms:

1. **Zero:**
   - `zero` → 0 (Special case: always requires confirmation).
   - "oh", "nought", "nil" are rejected (`NOT_A_NUMBER` / `UNSUPPORTED`).
2. **Units and Teens (1–19):**
   - `one`, `two`, `three`, `four`, `five`, `six`, `seven`, `eight`, `nine`, `ten`, `eleven`, `twelve`, `thirteen`, `fourteen`, `fifteen`, `sixteen`, `seventeen`, `eighteen`, `nineteen`.
3. **Tens (20, 30, ... 90):**
   - `twenty`, `thirty`, `forty`, `fifty`, `sixty`, `seventy`, `eighty`, `ninety`.
4. **Compound Tens (21–99):**
   - `T U` or `T-U` where `T` is a tens word and `U` is a unit word 1–9 (e.g. `twenty one`, `twenty-one`, `forty-five`, `ninety nine`).
5. **Hundreds (100–999):**
   - Count multiplier `M` (`one`–`nine` or `a`) + `hundred`.
   - Optional remainder (1–99): `M hundred [and] (1..99)` (e.g. `one hundred`, `a hundred`, `one hundred five`, `one hundred and five`, `one hundred fifty`, `one hundred and fifty`, `nine hundred ninety-nine`, `nine hundred and ninety-nine`).
6. **Teen Hundreds (1100–1999):**
   - Teen multiplier `T` (`eleven`–`nineteen`) + `hundred`.
   - Optional remainder (1–99): `T hundred [and] (1..99)` (e.g. `fifteen hundred`, `fifteen hundred fifty`, `fifteen hundred and fifty`, `nineteen hundred ninety-nine`).
7. **Thousands (1000–1999):**
   - Count multiplier `M` (`one` or `a`) + `thousand`.
   - Optional remainder (1–999):
     - Pure sub-100: `M thousand [and] (1..99)` (e.g. `one thousand five`, `one thousand and five`, `one thousand fifty`, `one thousand and fifty`, `a thousand and five`).
     - Hundreds without sub-100: `M thousand [and] H hundred` (e.g. `one thousand two hundred`, `one thousand and two hundred`, `a thousand five hundred`).
     - Hundreds with sub-100: `M thousand [and] H hundred [and] (1..99)` (e.g. `one thousand two hundred five`, `one thousand two hundred and five`, `one thousand and two hundred and five`, `a thousand two hundred and fifty`, `one thousand nine hundred ninety-nine`).
8. **Upper Bound (2000):**
   - `two thousand` → 2000.
9. **Canonical Digits (0–2000):**
   - Plain ASCII integer string from `0` to `2000` with no leading zeros (except `0`), no separators (commas), no decimals, and no signs (e.g. `0`, `45`, `100`, `1500`, `2000`).

### 7.2 Accepted Examples Summary

| Spoken Input | Value | Grammar Classification / Notes |
|---|---|---|
| `zero` | 0 | Standalone zero (default requires CONFIRM) |
| `one` … `nineteen` | 1–19 | Units and teens |
| `twenty`, `thirty`, … `ninety` | 20–90 | Multiples of ten |
| `forty-five` / `forty five` | 45 | Compound tens (tens + units 1–9) |
| `one hundred` / `a hundred` | 100 | Hundred with `one` or `a` multiplier |
| `one hundred five` / `one hundred and five` | 105 | Hundred + units (optional "and") |
| `one hundred fifty` / `one hundred and fifty` | 150 | Hundred + tens (optional "and") |
| `two hundred fifty` / `two hundred and fifty` | 250 | Hundreds digit 1–9 + remainder |
| `nine hundred ninety-nine` | 999 | Hundreds + compound tens |
| `one thousand` / `a thousand` | 1000 | Thousand with `one` or `a` multiplier |
| `one thousand five` / `one thousand and five` | 1005 | Thousand + units (optional "and") |
| `one thousand fifty` / `one thousand and fifty` | 1050 | Thousand + tens (optional "and") |
| `one thousand two hundred` / `one thousand and two hundred` | 1200 | Thousand + hundreds (optional "and", British/Indian English supported) |
| `one thousand two hundred five` / `one thousand two hundred and five` | 1205 | Thousand + hundreds + units |
| `one thousand two hundred and fifty` / `a thousand two hundred and fifty` | 1250 | Thousand + hundreds + tens |
| `one thousand nine hundred ninety-nine` | 1999 | Thousand + hundreds + compound tens |
| `fifteen hundred` | 1500 | Teen hundreds (`11`–`19` + `hundred`) |
| `fifteen hundred and fifty` / `fifteen hundred fifty` | 1550 | Teen hundreds + remainder 1–99 |
| `two thousand` | 2000 | Exact upper bound |
| `45`, `1500`, `2000` | 45, 1500, 2000 | Plain canonical digit strings |
| `forty five.`, `forty five?`, `forty five!` | 45 | Trailing sentence-level punctuation stripped |

### 7.3 Rejected Inputs & Reason Codes

Rejections are deterministic and return explicit reason codes. No guessing is permitted.

| Input | Reason Code | Reason & Classification Rule |
|---|---|---|
| `""`, `"   "` | `EMPTY` | Empty or whitespace-only input |
| `hello`, `undo`, `stop`, `yes`, `no`, `um`, `start`, `total`, `clear` | `NOT_A_NUMBER` | Non-number words, conversational speech, or command words |
| `dollars`, `rupees`, `cents`, `paise` | `NOT_A_NUMBER` | Currency words are out of scope |
| `two thousand and one`, `two thousand one`, `2001` | `OUT_OF_RANGE` | Valid numerical expression evaluating to 2001 (>2000) |
| `two thousand five hundred`, `twenty five hundred`, `2500` | `OUT_OF_RANGE` | Valid numerical expression evaluating to 2500 (>2000) |
| `three thousand`, `5000` | `OUT_OF_RANGE` | Valid numerical expression evaluating to >2000 |
| `minus five`, `negative ten`, `-5` | `UNSUPPORTED` | Negative numbers are not supported |
| `three point five`, `15.0`, `half`, `one fourth` | `UNSUPPORTED` | Decimals and fractions are not supported |
| `lakh`, `crore` | `UNSUPPORTED` | South Asian numbering units are out of scope for MVP |
| `hundred` (alone), `hundred fifty`, `thousand` (alone) | `MALFORMED` | Missing scale multiplier (requires `one` or `a`) |
| `ten hundred`, `twenty hundred`, `fifty hundred` | `MALFORMED` | Invalid scale multiplier (only 11–19 permitted for hundred) |
| `five hundred hundred`, `thousand thousand`, `one thousand thousand` | `MALFORMED` | Repeated/consecutive scale words |
| `hundred and`, `and fifty` | `MALFORMED` | Dangling/misplaced "and" |
| `forty and five` | `MALFORMED` | "and" is invalid between tens and units |
| `one thousand fifteen hundred` | `MALFORMED` | Cannot combine "thousand" with teen-hundred form |
| `007`, `05`, `1,500`, `1-500`, `٤٥` | `MALFORMED` | Non-canonical digit formatting (leading zeros, commas, non-ASCII) |
| `twenty twenty`, `fifteen fifty`, `thirteen fifty` | `AMBIGUOUS` | Compound year-style readings without scale words |
| `one twenty` | `AMBIGUOUS` / `MALFORMED` | Ambiguous reading without scale word |
| `one two three`, `four five`, `zero zero`, `double five` | `MULTIPLE_NUMBERS` / `AMBIGUOUS` | Disconnected digit sequences or repeated digit phrases |
| `forty five fifty`, `one hundred two hundred` | `MULTIPLE_NUMBERS` | Multiple distinct valid numbers in a single utterance |

### 7.4 Special Cases & Scope Boundaries

- **Zero Policy (DEFAULT):** A parsed `0` requires confirmation by default due to noise/silence risk.
- **Normalization Policy:** Trailing punctuation (`.`, `?`, `!`) is stripped only when sentence-final. Internal punctuation (`15.0`, `1,500`) is never stripped and causes a rejection.
- **Out of Scope:** Voice commands, currency symbols/words, decimals, negatives, non-English numbering systems (lakh/crore), and multiple numbers per utterance.

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

Targets marked **PROVISIONAL** are initial proposals; they must be reviewed and ratified by the user in a gate ADR (`research.md`). Never claim a target is met without a recorded measurement. On 2026-10-03 the Phase 5C gate (ADR-004) **ratified AC-4, AC-6, and AC-8 as written and amended AC-5** (the former absolute ≤20% bar is unattainable under the mandated confirm-all policy — see `research.md` §12 ADR-004).

| ID | Criterion | Measure |
|----|-----------|---------|
| AC-1 | Parser correctness | 100% of parser corpus passes: every integer 0–2000 round-trips from canonical word forms; all accepted variants in §7; all rejection cases in §7. |
| AC-2 | Arithmetic correctness | Calculation/undo/reset property-style tests pass; total always equals sum of non-undone accepted entries. |
| AC-3 | No silent doubtful additions | Decision engine tests prove: parse failure → REJECT; zero → CONFIRM; any rule-flagged uncertainty → CONFIRM/REJECT, never ACCEPT. |
| AC-4 | False Addition Rate (RATIFIED, ADR-004) | **0** wrong values added without user confirmation on a held-out test set of **≥ 500** utterances (target speaker, quiet room). Report N and the 95% upper bound (≈ 3/N when 0 errors). A non-zero result fails AC-4 and triggers redesign of thresholds/policy. |
| AC-5 | Usability (AMENDED, ADR-004) | Combined CONFIRM + REJECT rate on valid in-range utterances is **measured and reported** at the Phase 6.4 real-user trial. No absolute numeric bar until/unless Phase 5D (ADR-003) validates an auto-accept policy; AC-4 remains the inviolable safety bar and is never relaxed to compensate. |
| AC-6 | Latency (RATIFIED, ADR-004) | End-of-speech to UI result: p95 ≤ 1.5 s, max ≤ 3 s on target laptop. |
| AC-7 | Responsiveness | No GUI event-loop stall > 100 ms during listening/recognition (measured). |
| AC-8 | Stability (RATIFIED, ADR-004) | 60-minute continuous session: no crash; memory growth reported and ≤ 50 MB. |
| AC-9 | Offline | App runs with network disabled; no outbound connection attempts observed. |
| AC-10 | No voice commands | Test: non-number words (incl. "undo", "stop", "yes") produce REJECT and no state change. |
| AC-11 | Error recovery | Each error in §9 is triggered in manual testing; total/history preserved. |
| AC-12 | Packaging | Packaged Windows build passes AC-6/AC-9 smoke checks on a clean machine/profile. |
