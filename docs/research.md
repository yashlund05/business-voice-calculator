# Research — Experiment and Benchmark Log

> Doc role: **EVIDENCE**. Architecture hypotheses live in `architecture.md`; decisions that depend on this file are marked [BENCH] there.
> **Every table below is a TEMPLATE. All values are `PENDING` until a real experiment is run. Never fabricate, estimate, or copy numbers from the internet into results.** Record dataset size (N), settings, date, machine, and commit hash with every result.
> Raw data (recordings, labels, per-utterance CSVs) stays in git-ignored `data/`. Only summaries go here.

---

## 1. Research Objectives

| ID | Question | Used by | Status |
|----|----------|---------|--------|
| R1 | Can the baseline ASR (Vosk + grammar) hit acceptable Exact Integer Accuracy on the target speaker/environment? | Phase 3 ADR | PENDING |
| R2 | Does faster-whisper (tiny.en / base.en / small.en) outperform the baseline enough to justify size and latency? | Phase 3 ADR | PENDING |
| R3 | Does disagreement between two engines predict errors (hybrid hypothesis)? | Phase 3 ADR, Phase 5 | PENDING |
| R4 | Which VAD/segmentation settings minimize missed/clipped utterances and false triggers? | Phase 4 | PENDING |
| R5 | Is any signal (ASR confidence, duration, level, agreement) predictive of errors, and can an auto-accept rule reach 0 false additions on calibration data? | Phase 5 | PENDING |
| R6 | What are latency and resource use on the target laptop? | AC-6, AC-8 | PENDING |
| R7 | Is a 60-minute session stable? | AC-8 | PENDING |

## 2. Candidate ASR Models

| ID | Candidate | Config | Why considered | Model size on disk | Status |
|----|-----------|--------|----------------|--------------------|--------|
| A | Vosk small English (`vosk-model-small-en-us`) + constrained number grammar | grammar = number words list | fast, offline, constrained | PENDING | baseline, Phase 2 |
| B1 | faster-whisper `tiny.en`, CPU, int8 | no grammar; optional prompt bias (experimental) | small, general | PENDING | Phase 3 |
| B2 | faster-whisper `base.en`, CPU, int8 | same | accuracy/latency middle | PENDING | Phase 3 |
| B3 | faster-whisper `small.en`, CPU, int8 | same | higher accuracy, slower | PENDING | Phase 3 (optional) |
| C | Hybrid: A primary + B cross-check/second pass | offline agreement analysis first | agreement as validation signal | n/a | analysis only unless ADR approves |

Exact model versions/hashes are recorded when downloaded (outside the app, manually, into `models/`). Unlisted models are not evaluated unless added here with a reason.

## 3. Dataset and Recording Protocol

**Purpose:** a labeled local set of utterances representing real use. Collected with `tools/record_dataset.py`; stored in `data/recordings/` with `labels.csv` (`file, expected_value_or_NEGATIVE, category, speaker, session_id, split, notes`). Never committed, never uploaded.

**Conditions (match PRD):** Windows laptop built-in mic (and headset if the father will use one), quiet room, normal speaking distance, one number per utterance with a natural pause. Record at the app's sample rate (DEFAULT 16 kHz mono 16-bit, or record at native rate and resample consistently).

**Speakers:** primarily the real user (father) — essential; plus the developer. Record consent/awareness noted in `notes`. Accent/age effects are measured per speaker, not assumed.

**Content coverage (DEFAULT plan, adjust and document):**

| Category | Examples | Notes |
|----------|----------|-------|
| Units & teens | 0–19 | all values |
| Tens | 20, 30 … 90 | all |
| Confusable pairs | 13/30, 14/40, 15/50, 16/60, 17/70, 18/80, 19/90 | several repetitions each |
| Compound 21–99 | 21, 45, 67, 99 … | sample |
| Hundreds | 100, 200 … 900; "a hundred"; 101–999 incl. "and" variants | sample, include "one hundred and fifty", "two hundred fifty" |
| Thousands | 1000, "a thousand", 1001–1999, "fifteen hundred", 2000 | sample |
| Business-typical values | values the father actually adds (round numbers, prices) | ask the father |
| **Negative: out of range** | 2001, 2500, 5000, "minus five" | expected = NEGATIVE |
| **Negative: non-numbers** | "undo", "stop", "yes", "hello", "okay" | expected = NEGATIVE (verifies no voice commands) |
| **Negative: non-speech** | silence, room noise, cough, keyboard/typing, chair noise, breath | NEGATIVE |
| **Negative: malformed speech** | "hundred fifty", "twenty twenty", false starts, partial words | NEGATIVE |
| Variation | slower/faster speech, slightly louder/quieter, small distance changes | tag in `category` |

**Splits (separate by recording session, never by random utterance, to avoid leakage):**

| Split | Purpose | Minimum size (DEFAULT) | Rules |
|-------|---------|------------------------|-------|
| `dev` | development, debugging, VAD tuning | ≥ 200 utterances | free to inspect |
| `calibration` | choose thresholds/auto-accept rules (Phase 5) | ≥ 300 utterances | used for tuning only |
| `test` | final held-out evaluation (Phase 8.4) | ≥ 500 utterances (needed for AC-4 bound) | **not used for any tuning or model choice; run once per candidate final configuration**; if it is ever used to tune, record it here and collect a new test set |
| `train` | only if fine-tuning is ever approved | n/a | **not used in MVP** |

Include roughly 15–25% negative-class utterances in `calibration` and `test` (DEFAULT) so False Acceptance is measurable.

**Dataset record (fill in):**

| Field | Value |
|-------|-------|
| Recording date(s) | PENDING |
| Speakers | PENDING |
| Microphone(s) | PENDING |
| Room/noise notes | PENDING |
| dev / calibration / test sizes (valid + negative) | PENDING |

## 4. Benchmark Metrics

Ground truth per utterance: a valid integer v (0–2000) or `NEGATIVE`. "Added" means the decision policy under test would add the value to the total **without a user action** (auto-ACCEPT). With confirm-all policy no value is auto-added; the confirm path is measured separately.

| Metric | Definition |
|--------|-----------|
| **Exact Integer Accuracy (EIA)** | valid utterances where recognized text parses to exactly v ÷ valid utterances. (Pre-decision; measures ASR+parser.) |
| **False Addition Rate** | utterances where a **wrong value** (or any value for a NEGATIVE utterance) is added without user action ÷ all utterances. Primary safety metric. AC-4 target: 0, report N and upper bound. |
| **False Acceptance Rate** | auto-ACCEPT decisions that are wrong or on NEGATIVE ÷ all auto-ACCEPT decisions. (If no auto-ACCEPT occurs, report "n/a — auto-accept off".) |
| **Wrong-value-shown-at-confirm rate** | CONFIRM decisions displaying a value ≠ v (or on NEGATIVE) ÷ all CONFIRM decisions. Measures reliance on the human check. |
| **Rejection Rate** | REJECT ÷ valid utterances (burden), and correct-reject rate on NEGATIVE utterances (safety). |
| **Confirmation Rate** | CONFIRM ÷ valid utterances. |
| **End-to-end latency** | end-of-speech (VAD endpoint) → decision available to GUI; report p50, p95, max (ms). Also report ASR-only time. |
| **Resource usage** | peak and average CPU %, peak RSS (MB), model load time (s), model disk size (MB), on the target laptop. |
| **Long-session stability** | 60-min run: crashes, queue depth max, RSS at start/30/60 min, missed utterances, GUI stall max (ms). |

**Reporting rules:**
- Always report counts (e.g. `3/412`), not just percentages.
- For zero observed errors in N trials, report the approximate 95% upper bound ≈ 3/N (rule of three). Zero errors on a small N is not proof of safety.
- Break down by speaker and by category (confusable pairs, thousands, negatives).
- Report any utterance excluded and why. No post-hoc cherry-picking.

## 5. Experiment Template (copy per experiment)

```
### EXP-<nnn>: <title>
- Date / commit / machine:
- Question (link R#):
- Hypothesis:
- Dataset split & N (valid / negative):
- Configuration (engine, model, version, VAD settings, policy, thresholds):
- Procedure (commands):
- Results (counts + metrics, see §4):
- Observations (errors by category, examples by file name):
- Conclusion (supported / not supported / inconclusive):
- Follow-ups / next experiment:
- Raw outputs location (git-ignored):
```

**Experiment index**

| ID | Title | Date | Status | Outcome |
|----|-------|------|--------|---------|
| _none yet_ | | | | |

## 6. Results Table Template

Template — all `PENDING`.

| Exp | Engine/model | Policy | Split | N valid | N neg | EIA | False Additions (count/N) | False Acceptance | Wrong-at-confirm | Reject % | Confirm % | Latency p50/p95/max (ms) | Peak RAM (MB) |
|-----|--------------|--------|-------|---------|-------|-----|---------------------------|------------------|------------------|----------|-----------|--------------------------|---------------|
| PENDING | PENDING | confirm-all | dev | PENDING | PENDING | PENDING | PENDING | n/a | PENDING | PENDING | PENDING | PENDING | PENDING |

## 7. Model Comparison Template

Same dataset/split and same policy for every row. All `PENDING`.

| Metric | A: Vosk+grammar | B1: tiny.en | B2: base.en | B3: small.en | C: hybrid analysis |
|--------|-----------------|-------------|-------------|--------------|--------------------|
| EIA | PENDING | PENDING | PENDING | PENDING | PENDING |
| Errors on confusable pairs (count) | PENDING | PENDING | PENDING | PENDING | PENDING |
| Errors on thousands/hundreds (count) | PENDING | PENDING | PENDING | PENDING | PENDING |
| Output on NEGATIVE non-speech (hallucinated numbers, count) | PENDING | PENDING | PENDING | PENDING | PENDING |
| Output on NEGATIVE non-numbers (parsed as number, count) | PENDING | PENDING | PENDING | PENDING | PENDING |
| Latency p50 / p95 (ms) | PENDING | PENDING | PENDING | PENDING | PENDING |
| Model load time (s) | PENDING | PENDING | PENDING | PENDING | PENDING |
| Peak RAM (MB) | PENDING | PENDING | PENDING | PENDING | PENDING |
| Disk size (MB) | PENDING | PENDING | PENDING | PENDING | PENDING |
| Hybrid: of errors, % flagged by disagreement | n/a | n/a | n/a | n/a | PENDING |
| Hybrid: of correct, % falsely flagged by disagreement | n/a | n/a | n/a | n/a | PENDING |

## 8. VAD Experiment Template

**Baseline Implementation (Phase 3.2):**
- VAD detector: `EnergyVAD` (pure RMS energy thresholding, zero extra ML dependencies).
- Initial engineering defaults: Threshold = 500.0 RMS, Pre-roll = 250 ms, Hangover = 700 ms, Min/Max utterance = 250 ms / 6000 ms.
- Status: **Pending calibration on real speech dataset.** All accuracy and trigger measurements below are `PENDING`. No accuracy or quiet-room optimality is claimed without benchmark evidence.

Dataset: `dev` recordings + live trials. All `PENDING`.

| Exp | VAD (energy / Silero) | Threshold | Pre-roll (ms) | Hangover (ms) | Min/Max utt (ms) | Missed utterances | Clipped starts/ends | False triggers (noise) | Split utterances (one number → two) | Added dependency size |
|-----|-----------------------|-----------|---------------|---------------|------------------|-------------------|---------------------|------------------------|-------------------------------------|----------------------|
| PENDING | EnergyVAD | 500.0 RMS | 250 ms | 700 ms | 250 / 6000 ms | PENDING | PENDING | PENDING | PENDING | 0 MB (stdlib/numpy) |

Decision rule: adopt a heavier VAD only if it measurably improves missed/clipped/false-trigger counts on the same recordings and the dependency cost is justified in `memory.md`.

## 9. Confidence Calibration Record

Purpose: test whether any signal separates correct from incorrect recognitions. **Use the `calibration` split only.** ASR confidence is a hypothesis, not a trusted measure.

| Signal | Available from | Distribution on correct (N) | Distribution on wrong (N) | Separation (e.g. overlap, simple ROC description) | Usable? | Notes |
|--------|----------------|-----------------------------|----------------------------|---------------------------------------------------|---------|-------|
| ASR confidence | Vosk / Whisper (per engine) | PENDING | PENDING | PENDING | PENDING | |
| Utterance duration vs word count | segmenter | PENDING | PENDING | PENDING | PENDING | |
| Signal level (RMS/peak) | segmenter | PENDING | PENDING | PENDING | PENDING | |
| Engine agreement | A vs B | PENDING | PENDING | PENDING | PENDING | |
| N-best disagreement | engine | PENDING | PENDING | PENDING | PENDING | |

**Candidate auto-accept rules tested:**

| Rule ID | Description | Calibration N | Auto-accepted | Wrong among accepted | Confirm % | Reject % | Verdict |
|---------|-------------|---------------|---------------|----------------------|-----------|----------|---------|
| _none yet_ | | | | | | | |

Policy: a rule is eligible for use only if it yields 0 wrong among accepted on calibration data **and** the same rule is later evaluated unchanged on the `test` split. Failure on test → rule removed or redesigned and a new test set collected.

## 10. Failed Experiment Log

Record dead ends so they are not repeated.

| ID | What was tried | Why it failed (evidence) | Date | Don't retry unless… |
|----|----------------|--------------------------|------|----------------------|
| _none yet_ | | | | |

## 11. Architecture Decision Record (ADR) Template

```
### ADR-<nnn>: <decision title>
- Date:
- Status: Proposed | Accepted | Superseded by ADR-<n>
- Context (requirement/risk driving the decision; link prd/architecture sections):
- Options considered:
- Evidence (experiment IDs, tables, N, splits):
- Decision:
- Consequences (benefits, costs, risks, what we now must/mustn't do):
- Residual risks / follow-up:
- Approved by (user): <name/date>   <- required for ASR choice and any change to a FIXED requirement
```

## 12. ADR Log

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| ADR-001 | ASR engine and model strategy | PENDING (Phase 3.4) | — |
| ADR-002 | VAD choice and segmentation settings | PENDING (Phase 4) | — |
| ADR-003 | Auto-accept policy (on/off, rules) | PENDING (Phase 5) | — |
| ADR-004 | Ratification of PROVISIONAL targets in `prd.md` §13 | PENDING (Phase 3 gate) | — |
| ADR-005 | Packaging mode (one-folder vs one-file) | PENDING (Phase 8) | — |

## 13. Long-Session Stability Record (template)

| Run | Date | Duration | Config/commit | Crashes | Max queue depth | RSS start / 30 min / 60 min (MB) | Max GUI stall (ms) | Missed utterances (if known) | Notes |
|-----|------|----------|---------------|---------|-----------------|----------------------------------|--------------------|------------------------------|-------|
| PENDING | | | | | | | | | |
