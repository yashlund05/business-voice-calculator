# Benchmark Results Artifacts

This directory contains committed summary and comparison JSON artifacts from empirical ASR and parser benchmarks executed on the Dad speech dataset (`data/processed_phone/benchmark_dad/`).

> **Privacy & Offline Notice:** No raw audio recordings, WAV files, or binary model weights are committed to Git. Only structured numeric evaluation metrics, performance summaries, and latency measurements are preserved here.

---

## Artifact Index

| Artifact File | Benchmark Stage / Phase | Description |
| :--- | :--- | :--- |
| `summary.json` | **Phase 4B Baseline** | Baseline evaluation of Vosk CPU on 61 eligible Dad utterances (before Phase 4C natural speech parser expansion). |
| `summary_vosk_cpu.json` | **Phase 4C Re-Benchmark** | Re-evaluation of Vosk CPU on identical 61 eligible Dad utterances following deterministic parser expansion (bare `hundred` and `thousand` support). |
| `summary_whisper_tiny_cpu_1t.json` | **Phase 4B / 4C** | Evaluation of `faster-whisper-tiny.en` on CPU with **1 worker thread** (`int8` quantization). |
| `summary_whisper_tiny_cpu_2t.json` | **Phase 4B / 4C** | Evaluation of `faster-whisper-tiny.en` on CPU with **2 worker threads** (`int8` quantization). |
| `summary_whisper_tiny_cpu_4t.json` | **Phase 4B / 4C** | Evaluation of `faster-whisper-tiny.en` on CPU with **4 worker threads** (`int8` quantization). |
| `low_end_asr_comparison.json` | **Phase 4B / 4C Unified Report** | Unified side-by-side metric comparison, latency distributions, and category breakdowns across all evaluated configurations. |

---

## Benchmark Dataset Summary

- **Audio Source:** Slower-than-working-speed continuous phone recording of father speaking numbers 0–2000 (105.77s mono 16 kHz PCM).
- **Segmentation:** 62 segmented single-number utterances (`prompt_001.wav` to `prompt_062.wav`).
- **Primary Evaluation Set:** **61 eligible utterances** (Prompt 16 excluded from primary metrics due to omitted speech window).
- **Safety Policy:** Confirm-All default (`AUTO_ACCEPT_ENABLED = False`). **Zero False Additions** observed across all configurations.

### Key Benchmark Metrics Overview

| Metric | Phase 4B Vosk Baseline | Phase 4C Vosk (Natural Grammar) | faster-whisper tiny.en (4t) |
| :--- | :---: | :---: | :---: |
| **Exact Integer Accuracy (EIA)** | **47.54%** (29/61) | **57.38%** (35/61) | **62.30%** (38/61) |
| **Wrong Parsed Value Rate** | **8.20%** (5/61) | **11.48%** (7/61) | **13.11%** (8/61) |
| **Parser Rejection Rate** | **44.26%** (27/61) | **31.15%** (19/61) | **24.59%** (15/61) |
| **Safe Failure Rate** | **91.80%** (56/61) | **88.52%** (54/61) | **86.89%** (53/61) |
| **Median CPU Latency** | **26.1 ms** | **32.8 ms** | **418.2 ms** |
| **Peak RAM RSS** | **180.95 MB** | **180.95 MB** | **402.67 MB** |

---

## Note on Local Paths in JSON Artifacts

Some summary JSON artifacts include fields referencing local filesystem paths (e.g. `data/processed_phone/benchmark_dad/manifest.csv` or absolute model directory paths). These paths were generated automatically by the offline benchmark runner (`data/processed_phone/analysis/benchmark_low_end_cpu.py`) during local execution. In accordance with project source-of-truth integrity rules, the raw generated JSON summaries are preserved verbatim without manual editing.
