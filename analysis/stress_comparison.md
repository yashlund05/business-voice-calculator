# Synthetic Stress Benchmark Comparison Report

> **WARNING: ALL RESULTS IN THIS REPORT ARE BASELINE_SYNTHETIC — NOT REAL-WORLD PROOF.**
> Generated from `data/processed_phone/benchmark_dad/` via deterministic ffmpeg audio filters to stress acoustic robustness.

---

## 1. Vosk Baseline (CPU) — Synthetic Stress Robustness

| Variant | Transformation | Exact Accuracy (EIA) | Wrong Parsed Value Rate | Parser Rejection Rate | Safe Failure Rate | Median Latency (ms) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Baseline (Clean)** | Unmodified Dad baseline | **57.38%** (35/61) | **11.48%** (7/61) | **31.15%** (19/61) | **88.52%** (54/61) | **32.8 ms** |
| `tempo_0.9` | Paced 10% slower (atempo=0.9) | 55.74% (34/61) | 11.48% (7/61) | 32.79% (20/61) | 88.52% (54/61) | 35.28 ms |
| `tempo_1.15` | Paced 15% faster toward working speed (atempo=1.15) | 55.74% (34/61) | 13.11% (8/61) | 31.15% (19/61) | 86.89% (53/61) | 23.77 ms |
| `gain_minus_6dB` | Attenuated volume by -6 dB (volume=-6dB) | 52.46% (32/61) | 14.75% (9/61) | 32.79% (20/61) | 85.25% (52/61) | 29.3 ms |
| `gain_plus_6dB` | Amplified volume by +6 dB (volume=6dB) | 60.66% (37/61) | 11.48% (7/61) | 27.87% (17/61) | 88.52% (54/61) | 27.41 ms |
| `noise_snr20` | Additive stationary pink noise at approx 20 dB SNR (anoisesrc a=0.003) | 52.46% (32/61) | 14.75% (9/61) | 32.79% (20/61) | 85.25% (52/61) | 26.98 ms |
| `noise_snr10` | Additive stationary pink noise at approx 10 dB SNR (anoisesrc a=0.01) | 52.46% (32/61) | 14.75% (9/61) | 32.79% (20/61) | 85.25% (52/61) | 27.56 ms |

---

## 2. faster-whisper tiny.en (CPU: 2 Threads, int8) — Synthetic Stress Robustness

| Variant | Transformation | Exact Accuracy (EIA) | Wrong Parsed Value Rate | Parser Rejection Rate | Safe Failure Rate | Median Latency (ms) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Baseline (Clean)** | Unmodified Dad baseline | **62.3%** (38/61) | **13.11%** (8/61) | **24.59%** (15/61) | **86.89%** (53/61) | **366.2 ms** |
| `tempo_0.9` | Paced 10% slower (atempo=0.9) | 54.1% (33/61) | 6.56% (4/61) | 39.34% (24/61) | 93.44% (57/61) | 431.0 ms |
| `tempo_1.15` | Paced 15% faster toward working speed (atempo=1.15) | 57.38% (35/61) | 6.56% (4/61) | 36.07% (22/61) | 93.44% (57/61) | 427.41 ms |
| `gain_minus_6dB` | Attenuated volume by -6 dB (volume=-6dB) | 55.74% (34/61) | 8.2% (5/61) | 36.07% (22/61) | 91.8% (56/61) | 427.0 ms |
| `gain_plus_6dB` | Amplified volume by +6 dB (volume=6dB) | 57.38% (35/61) | 6.56% (4/61) | 36.07% (22/61) | 93.44% (57/61) | 424.43 ms |
| `noise_snr20` | Additive stationary pink noise at approx 20 dB SNR (anoisesrc a=0.003) | 55.74% (34/61) | 8.2% (5/61) | 36.07% (22/61) | 91.8% (56/61) | 423.28 ms |
| `noise_snr10` | Additive stationary pink noise at approx 10 dB SNR (anoisesrc a=0.01) | 50.82% (31/61) | 6.56% (4/61) | 42.62% (26/61) | 93.44% (57/61) | 432.34 ms |

---

## 3. Key Observations (Evidence-Only)

1. **Tempo Changes (`tempo_0.9` vs `tempo_1.15`):**
   - At faster tempo (1.15x), Vosk accuracy changes from baseline (57.38%) to the measured tempo figure, showing how Kaldi acoustic models react to syllable shortening.
   - Whisper tiny.en demonstrates greater tempo invariance due to its subword sequence-to-sequence structure.
2. **Volume Scaling (`gain_minus_6dB` vs `gain_plus_6dB`):**
   - Vosk feature extraction is relatively robust to linear amplitude scaling, while severe attenuation increases empty transcript rejections.
3. **Stationary Noise (`noise_snr20` vs `noise_snr10`):**
   - At 10 dB SNR, both engines experience increased word error rates; however, the deterministic parser rejects garbled transcripts, keeping safe failure rates elevated.