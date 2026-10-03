# Research — Experiment and Benchmark Log

> Doc role: **EVIDENCE**. Architecture hypotheses live in `architecture.md`; decisions that depend on this file are marked [BENCH] there.
> **Every table below is a TEMPLATE. All values are `PENDING` until a real experiment is run. Never fabricate, estimate, or copy numbers from the internet into results.** Record dataset size (N), settings, date, machine, and commit hash with every result.
> Raw data (recordings, labels, per-utterance CSVs) stays in git-ignored `data/`. Only summaries go here.

---

## 1. Research Objectives

| ID | Question | Used by | Status |
|----|----------|---------|--------|
| R1 | Can the baseline ASR (Vosk + grammar) hit acceptable Exact Integer Accuracy on the target speaker/environment? | Phase 3 ADR | MEASURED: EIA 57.38% on Dad dataset (EXP-002/003); "acceptable" target pending ADR-004 ratification |
| R2 | Does faster-whisper (tiny.en / base.en / small.en) outperform the baseline enough to justify size and latency? | Phase 3 ADR | ANSWERED: No for default deployment — tiny.en measured higher wrong-value rate, 12–14× latency, ~2× RAM (EXP-002/004/005); rejected by ADR-001. B2/B3 never benchmarked. |
| R3 | Does disagreement between two engines predict errors (hybrid hypothesis)? | Phase 3 ADR, Phase 5 | PARTIAL: oracle union 73.8% measured (EXP-004); no per-utterance selection signal exists yet (R5 pending); hybrid not adopted for MVP (ADR-001) |
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
| EXP-001 | Analysis of Dad's Continuous Phone Recording & Baseline VAD Segmentation | 2026-10-02 | Completed | Baseline VAD (500 RMS / 700ms hangover) kept speech active across pauses due to 450-550 RMS room floor, hitting 6.0s max utterance cap on 16/20 segments. Mapped 62 spoken prompts in audio. Demonstrated need for calibrated VAD threshold/hangover or discrete utterance slicing for single-utterance benchmarking. |
| EXP-002 | Low-End CPU ASR Benchmark: Vosk Baseline vs faster-whisper tiny.en (1/2/4 threads) on Dad Speech Baseline | 2026-10-02 | Completed | Evaluated on identical 61 eligible Dad utterances (slower-than-working-speed): Vosk CPU (EIA=47.54%, Wrong=8.20%, Rej=44.26%, Safe=91.80%, Median Latency=26.1ms, Peak RSS=180.95MB); tiny.en CPU across 1/2/4 threads (EIA=62.30%, Wrong=13.11%, Rej=24.59%, Safe=86.89%, Latency: 1t=557.1ms, 2t=366.2ms, 4t=323.6ms, Peak RSS=363.89MB to 407.89MB). Critical finding: tiny.en increased raw accuracy (+14.76%) on natural hundred forms but produced a 60% higher wrong-number rate (13.11% vs 8.20%), dropping leading thousand multipliers (e.g. 1750->750, 1200->200). Vosk proved safer by design (91.80% vs 86.89% safe failure rate) and 12.4x faster on CPU. |
| EXP-003 | Natural Speech Parser Expansion & Controlled Vosk Re-Benchmark | 2026-10-02 | Completed | Deterministic parser extended for natural bare hundred/thousand forms ('hundred', 'hundred ten', 'hundred twenty five', 'hundred fifty', 'hundred seventy five', 'thousand'). Vosk re-benchmark on identical 61 eligible Dad recordings: EIA increased from 47.54% to 57.38% (+9.84% gain, +6 correct numbers parsed with 0 added compute/ML complexity). Rejection rate dropped from 44.26% to 31.15%. Wrong parsed values rose from 8.20% (5/61) to 11.48% (7/61) due to ASR deletion of leading multipliers ('two thousand' transcribed as 'thousand' -> 1000; 'twelve hundred fifty' transcribed as 'hundred fifteen' -> 115). Safe failure rate remains high at 88.52% (vs Whisper 86.89%). Proves 22% of Vosk's baseline rejections were purely grammar-induced and recoverable safely by deterministic parsing. |
| EXP-004 | Error Taxonomy Audit & Engine Complementarity Analysis | 2026-10-02 | Completed | Classified all 61 eligible Dad utterances into formal taxonomy across Vosk and faster-whisper tiny.en (2t). Vosk errors concentrate in empty transcripts (11.5%) and phonetic confusions (6.6%), whereas Whisper tiny.en errors concentrate in word drops (6.6%) and digit hallucinations (4.9%). Both engines correct on 28/61 (45.9%); Vosk-only correct on 7/61 (11.5%); Whisper-only correct on 10/61 (16.4%); both failed/rejected on 16/61 (26.2%). Theoretical oracle union is 45/61 (73.8%). Containment verified: 0/15 wrong parsed values auto-added. Full logs in analysis/error_audit.md. |
| EXP-005 | Synthetic Stress Benchmark: Tempo, Volume, and Stationary Noise Robustness | 2026-10-02 | Completed | Evaluated 6 synthetic audio variants (tempo 0.9x/1.15x, gain +/-6dB, pink noise SNR 20dB/10dB) on 61 Dad prompts. Vosk EIA ranged 52.46% to 60.66% with median latency 23.8-35.3 ms. Whisper tiny.en (2t) EIA ranged 50.82% to 57.38% with median latency 423-432 ms. Thread scaling showed negative returns past 2 threads on target CPU. Severe noise/attenuation increased rejections, maintaining safe failure rates >= 85.25% in all conditions. Full report in analysis/stress_comparison.md. |

## 6. Results Table Template

Template — all `PENDING`.

| Exp | Engine/model | Policy | Split | N valid | N neg | EIA | False Additions (count/N) | False Acceptance | Wrong-at-confirm | Reject % | Confirm % | Latency p50/p95/max (ms) | Peak RAM (MB) |
|-----|--------------|--------|-------|---------|-------|-----|---------------------------|------------------|------------------|----------|-----------|--------------------------|---------------|
| PENDING | PENDING | confirm-all | dev | PENDING | PENDING | PENDING | PENDING | n/a | PENDING | PENDING | PENDING | PENDING | PENDING |

## 7. Model Comparison Template

Same dataset/split and same policy for every row. All empirical metrics `PENDING` user speech recordings.

| Metric | A: Vosk+grammar (Default) | B1: tiny.en | B2: base.en (Candidate) | B3: small.en | C: hybrid analysis |
|--------|-----------------|-------------|-------------|--------------|--------------------|
| EIA | PENDING | PENDING | PENDING | PENDING | PENDING |
| Errors on confusable pairs (count) | PENDING | PENDING | PENDING | PENDING | PENDING |
| Errors on thousands/hundreds (count) | PENDING | PENDING | PENDING | PENDING | PENDING |
| Output on NEGATIVE non-speech (hallucinated numbers, count) | PENDING | PENDING | PENDING | PENDING | PENDING |
| Output on NEGATIVE non-numbers (parsed as number, count) | PENDING | PENDING | PENDING | PENDING | PENDING |
| Latency p50 / p95 (ms) | PENDING | PENDING | PENDING | PENDING | PENDING |
| Model load time (s) | PENDING (~1.9s) | PENDING | PENDING | PENDING | PENDING |
| Peak RAM / VRAM (MB) | PENDING (~50MB RAM) | PENDING | PENDING | PENDING | PENDING |
| Disk size (MB) | ~50 MB | ~75 MB | ~140 MB | ~460 MB | PENDING |
| Hybrid: of errors, % flagged by disagreement | n/a | n/a | n/a | n/a | PENDING |
| Hybrid: of correct, % falsely flagged by disagreement | n/a | n/a | n/a | n/a | PENDING |

### Phase 4A Candidate Infrastructure Summary:
- **faster-whisper Candidate Engine:** `FasterWhisperEngine` implemented in `src/voice_calculator/asr/whisper_engine.py` conforming to `ASREngine`.
- **Target Hardware Constraints:** Windows 11, NVIDIA RTX 3050 Laptop GPU (4 GB VRAM), 20 GB RAM, Python 3.11.
- **Recommended Candidate Model:** `faster-whisper-base.en` (compact ~140MB CTranslate2 model, highly efficient on 4GB VRAM in `float16`/`int8_float16` or multi-threaded CPU `int8`).
- **Benchmark Command:**
  * Vosk baseline: `python tools/benchmark.py --engine vosk --dataset-dir data/recordings`
  * faster-whisper candidate: `python tools/benchmark.py --engine faster-whisper --dataset-dir data/recordings --device cpu --compute-type int8` (or `--device cuda --compute-type float16`)
- **Uncalibrated Score Invariant:** Raw Whisper logprobs and token probabilities are uncalibrated and returned as `confidence = None`. Auto-accept is strictly prohibited without empirical calibration data. Vosk remains the default engine.

## 8. VAD Experiment & Calibration Record

**Baseline Implementation (Phase 3.2 & 3.8):**
- VAD detector: `EnergyVAD` (pure RMS energy thresholding, zero extra ML dependencies).
- Initial engineering defaults: Threshold = 500.0 RMS, Pre-roll = 250 ms, Hangover = 700 ms, Min/Max utterance = 250 ms / 6000 ms.
- **Phase 3.8 Calibration Findings & Bug Fix:**
  - *Onset speech duration tracking fix:* Resolved an issue in `UtteranceSegmenter` where `_speech_duration_ms` previously summed all frames in `_speech_frames` (including the 250 ms pre-roll silence buffer) upon speech onset. This caused short transient clicks (e.g. 30 ms key tap) to immediately meet the `min_utterance_ms = 250 ms` threshold. Fixed by initializing `_speech_duration_ms = frame.duration_ms` for active speech only, while preserving full pre-roll audio in the finalized PCM output for onset consonant preservation.
  - *Quiet speech evaluation:* RMS threshold of 500.0 reliably detects clear speech (>800 RMS) but may miss quiet speech (<500 RMS) on unamplified microphones. Calibration on recorded user speech is required to tune gain and threshold.
  - *Pauses within compound numbers:* The 700 ms hangover window successfully accommodates intra-phrase pauses (e.g. "one hundred ... fifty") without splitting numbers into multiple utterances.
  - *Duration caps:* 6000 ms max utterance cap reliably triggers `TOO_LONG` and `DecisionReason.UTTERANCE_TOO_LONG`, safely preventing continuous ambient noise from corrupting state.

Dataset: `dev` recordings + live trials. All empirical dataset numbers `PENDING` real speech collection.

| Exp | VAD (energy / Silero) | Threshold | Pre-roll (ms) | Hangover (ms) | Min/Max utt (ms) | Missed utterances | Clipped starts/ends | False triggers (noise) | Split utterances (one number → two) | Added dependency size |
|-----|-----------------------|-----------|---------------|---------------|------------------|-------------------|---------------------|------------------------|-------------------------------------|----------------------|
| EXP-001 (Phase 3.8) | EnergyVAD | 500.0 RMS | 250 ms | 700 ms | 250 / 6000 ms | PENDING (real dataset) | 0 clipped in unit tests | Fixed onset noise leak | 0 splits observed on <700ms pause | 0 MB (stdlib/numpy) |

Decision rule: adopt a heavier VAD only if it measurably improves missed/clipped/false-trigger counts on the same recordings and the dependency cost is justified in `memory.md`.

## 9. Confidence Calibration Record

Purpose: test whether any signal separates correct from incorrect recognitions. **Use the `calibration` split only.** ASR confidence is a hypothesis, not a trusted measure.

**Candidate Safety & Policy Boundary Note (Phase 3.4, 3.7 & 3.8):**
- In `SafetyDecisionEngine`, confidence thresholds (`min_confidence`) and confidence requirements (`require_confidence`) exist as policy boundaries.
- **Current status:** Confidence scores are **uncalibrated** and not empirically validated. ASR confidence alone is NEVER treated as proof of correctness.
- When ASR confidence is missing (such as the current Vosk baseline) or uncalibrated, the safety layer deterministically falls back to conservative confirm-by-default behavior (`requires_confirmation = True`) in both Safe Mode and Fast Mode.
- No claims of "confidence > X implies accuracy" are made without measured benchmark calibration data.

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
| ADR-001 | ASR engine and model strategy | **ACCEPTED** | 2026-10-03 |
| ADR-002 | VAD choice and segmentation settings | PENDING (Phase 5D) | — |
| ADR-003 | Auto-accept policy (on/off, rules) | PENDING (Phase 5D) | — |
| ADR-004 | Ratification of PROVISIONAL targets in `prd.md` §13 | **ACCEPTED** (AC-4/6/8 ratified; AC-5 amended) | 2026-10-03 |
| ADR-005 | Packaging mode (one-folder vs one-file) | PENDING (Phase 6) | — |

### ADR-001: ASR engine and model strategy (resolves pending decision P2)
- Date: 2026-10-03
- Status: Accepted
- Context: FIXED requirements demand fully offline English recognition of 0–2000 on Windows, with prevention of silent wrong additions prioritized over convenience (`prd.md`, `AGENTS.md` §1). The standing Low-End-First Directive (`memory.md` decision #22) makes CPU-only execution on older/budget Windows laptops the primary deployment path — no mandatory GPU. The `ASREngine` protocol keeps engines modular (`architecture.md` §8). The decision required here: which engine ships as the v1 default (options A/B/C, `architecture.md` §8), based on measured evidence rather than popularity or recency (`AGENTS.md` §8).
- Options considered:
  * **A.** Vosk small English (`vosk-model-small-en-us`) + constrained number-word grammar (baseline, Phase 2.2).
  * **B1.** faster-whisper `tiny.en`, CPU int8 (integrated as candidate, Phase 4A). B2 `base.en` / B3 `small.en` were to be evaluated only if B1 showed promise; they were **not** benchmarked.
  * **C.** Hybrid: A primary + B cross-check / agreement gating (analysis only, `research.md` §2 row C).
- Evidence (all N=61 eligible Dad dataset utterances, identical audio; `analysis/error_audit.md`, `analysis/stress_comparison.md`):
  * **EXP-002:** Vosk EIA 47.54% (29/61), wrong-parsed-value 8.20% (5/61), median latency 26.1 ms, peak RSS 180.95 MB. tiny.en (CPU) EIA 62.30% (38/61), wrong 13.11% (8/61), median latency 323.6–557.1 ms across 1/2/4 threads, peak RSS 363.89–407.89 MB.
  * **EXP-003:** deterministic parser expansion lifted Vosk to EIA 57.38% (35/61), rejections 44.26%→31.15%, wrong 11.48% (7/61) — at zero runtime cost. The EIA gap to tiny.en narrowed to 4.92 pp while Vosk kept the lower wrong-value rate (11.48% vs 13.11%).
  * **EXP-004 (error taxonomy):** Vosk's errors are dominated by *safe failures* — empty transcripts (11.5%) and malformed structures (13.1%) that the parser rejects — plus confusable-pair confusions (6.6%). tiny.en's signature failures are word drops (6.6%, e.g. 1750→750, 1200→200) and hallucinated digit strings (4.9%, e.g. 60→"660", 90→"990", 80→"808") — both produce plausible, in-range, **wrong numbers, the most dangerous error class for this product**. Complementarity: both-correct 28/61, Vosk-only 7/61, tiny.en-only 10/61, both-failed 16/61; oracle union 73.8% is an upper bound only — no per-utterance selection signal exists (R3/R5 unmeasured).
  * **EXP-005 (synthetic stress, 6 variants):** Vosk EIA 52.46–60.66%, median latency 23.8–35.3 ms; tiny.en (2t) EIA 50.82–57.38%, median 423–432 ms; thread scaling past 2 threads showed negative returns; safe failure ≥85.25% in all conditions.
  * **Confidence invariant:** both engines expose uncalibrated confidence (`None`), so confirm-by-default is forced regardless of engine (`architecture.md` §9). The engine choice therefore cannot change the safety policy today — it changes accuracy-at-confirm, rejection burden, latency, and resource use.
- Decision: **Adopt Option A — Vosk small English + constrained number-word grammar — as the default deployed ASR engine.** Option B1 remains integrated behind `ASREngine` as a benchmarkable candidate (not the shipped default). Option C is not adopted for MVP: the 73.8% oracle assumes a per-utterance correctness signal that does not exist (R3/R5 pending), and it would roughly double latency/memory and add a second model dependency for an unproven benefit (`AGENTS.md` §8: do not add a second ASR model merely because it sounds theoretically safer).
- Rationale (why A under the Low-End-First Directive):
  1. **Lowest wrong-value risk profile:** 7/61 wrong vs 8/61, and Vosk's residual errors are dominated by safely rejected structures, whereas tiny.en uniquely hallucinates valid-looking numbers and drops leading multipliers.
  2. **12–14× lower median latency** (26–35 ms vs 324–557 ms), leaving enormous headroom against AC-6 (p95 ≤ 1.5 s) even on much weaker CPUs — tiny.en's margins were measured on the development machine, not the low-end target.
  3. **~2× less RAM** (181 MB vs 364–408 MB peak RSS) and ~50 MB vs ~75 MB on disk — often the difference between fitting and straining on budget hardware.
  4. **Grammar-constrained decoding** bounds output to number words, structurally limiting free-form hallucination.
  5. The 4.92 pp EIA gap is partly a parser problem, not an acoustic one — deterministic grammar work already recovered +9.84 pp at zero runtime cost (EXP-003), and that lever stays open.
- Consequences (what we now must/mustn't do):
  * Vosk small is the engine assumed by ADR-002 (VAD calibration) and ADR-003 (auto-accept policy).
  * `FasterWhisperEngine` stays modular and benchmarkable (`tools/benchmark.py --engine faster-whisper`) but is not the default; whether it ships in the packaged distribution is a follow-up to ADR-005.
  * Auto-accept (Fast Mode) remains impossible until Phase 5D validates a rule (both engines return `confidence=None` today).
  * Confusable pairs (13/30 … 19/90; 6.6% error on this dataset) are Vosk's known weak spot — the confirmation step is the mitigation.
  * Parser grammar expansion remains the cheapest accuracy lever (4C pattern) and stays open.
- Residual risks / follow-up:
  * The evidence base is one speaker (N=61, phone recording); this ADR is bounded to that dataset — re-open after the Phase 6.4 trial or when new recordings exist.
  * B2/B3 were never benchmarked; if tiny.en-class engines are reconsidered, benchmark B2/B3 on the same dataset first.
  * If Phase 5D validates a reliable correctness signal, the tiny.en-only-correct cases (10/61) could justify revisiting the hybrid option under a new ADR.
- Approved by (user): user directive to proceed with Phase 5C ("move ahead to next step"), 2026-10-03; decision follows the standing Low-End-First Directive (`memory.md` decision #22, 2026-10-02).

### ADR-004: Ratification of PROVISIONAL acceptance targets in `prd.md` §13 (resolves pending decision P5)
- Date: 2026-10-03
- Status: Accepted (user selected "Amend AC-5" at the Phase 5C gate)
- Context: `prd.md` §13 marks AC-4, AC-5, AC-6, AC-8 as PROVISIONAL, requiring user ratification at a gate ADR. Measured evidence now exists to judge attainability (EXP-002…005; 61-utterance Dad dataset; ADR-001 engine decision).
- Evidence:
  * **AC-4 (0 false additions without user confirmation; held-out set ≥ 500):** currently satisfied structurally — confirm-by-default policy, `AUTO_ACCEPT_ENABLED = False`, and 0/15 wrong values auto-added (EXP-004 containment audit). The ≥ 500-utterance held-out set does not yet exist (new recording sessions cancelled in Phase 4E for time constraints).
  * **AC-5 (≤ 20% combined CONFIRM+REJECT on valid utterances):** unattainable under the mandated confirm-all policy — while confidence is uncalibrated (both engines return `None`), every parsed valid utterance produces a CONFIRM prompt, so CONFIRM+REJECT = 100% by construction. Even a perfect auto-accept selector would need ≥ 80% correct auto-adds; the best measured single-engine EIA is 57.38% (Vosk, EXP-003) and the theoretical two-engine oracle union is 73.8% (EXP-004) — below 80%.
  * **AC-6 (p95 ≤ 1.5 s, max ≤ 3 s):** strongly supported — Vosk median latency 26–35 ms on CPU (EXP-002/005), orders of magnitude under budget.
  * **AC-8 (60-min session, no crash, ≤ 50 MB growth):** not yet measured (Phase 6.1 soak pending); no contrary evidence.
- Decision (user-ratified, 2026-10-03):
  * **AC-4 RATIFIED as written.** The ≥ 500-utterance held-out verification remains a Phase 6 obligation; its collection scope must be planned at 6.4 given the Phase 4E cancellation.
  * **AC-5 AMENDED.** The absolute ≤ 20% bar is removed. New measure: "Combined CONFIRM + REJECT rate on valid in-range utterances is measured and reported at the Phase 6.4 real-user trial; AC-4 remains the inviolable safety bar and is never relaxed to compensate. A numeric usability bar may be reinstated only if Phase 5D validates an auto-accept policy (ADR-003)."
  * **AC-6 RATIFIED as written.**
  * **AC-8 RATIFIED as written** (verification pending the Phase 6.1 soak).
- Consequences: `prd.md` §13 updated accordingly. Fast Mode stays confirm-only until ADR-003 produces a validated rule. Usability progress is tracked as reported metrics from the trial rather than a pass/fail numeric gate.
- Residual risks: with no numeric usability bar, the interaction burden (one confirmation per number) must be watched closely in the 6.4 trial; if the burden proves unacceptable, the correct response is better recognition accuracy (parser/ASR work), never relaxing AC-4.
- Approved by (user): "Amend AC-5" option selected at the Phase 5C gate, 2026-10-03.

## 13. Long-Session Stability Record (template)

| Run | Date | Duration | Config/commit | Crashes | Max queue depth | RSS start / 30 min / 60 min (MB) | Max GUI stall (ms) | Missed utterances (if known) | Notes |
|-----|------|----------|---------------|---------|-----------------|----------------------------------|--------------------|------------------------------|-------|
| PENDING | | | | | | | | | |
