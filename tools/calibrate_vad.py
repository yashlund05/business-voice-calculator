"""Phase 5D (EXP-006): VAD threshold/hangover calibration on the continuous Dad recording.

Feeds `data/processed_phone/dad_continuous_16k.wav` through the production
UtteranceSegmenter + EnergyVAD for a grid of (threshold, hangover) settings and
scores each configuration against ground-truth speech intervals parsed from
`analysis/error_audit.csv` notes ("Spoken as '...' (S-Es)").

Scoring per configuration:
- clean         : ground-truth interval captured by exactly one segment that contains no other interval
- split         : ground-truth interval overlapped by >= 2 segments (one number broken into pieces)
- merged        : one segment overlaps >= 2 ground-truth intervals (multiple numbers in one utterance)
- missed        : ground-truth interval with no overlapping segment
- false_trigger : segment overlapping no ground-truth interval
- cap_hits      : segments reaching the 6000 ms max-utterance cap

Offline, deterministic, privacy-safe (no audio leaves the machine; no transcripts logged).
Output: markdown table to stdout + `analysis/vad_calibration.csv`.

Usage (repo root):
    python tools/calibrate_vad.py
"""

import csv
import re
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from voice_calculator.audio.capture import AudioFrame  # noqa: E402
from voice_calculator.audio.segmenter import UtteranceSegmenter  # noqa: E402
from voice_calculator.audio.vad import EnergyVAD  # noqa: E402
from voice_calculator.audio.wavio import read_wav  # noqa: E402
from voice_calculator.config import (  # noqa: E402
    AUDIO_BLOCK_DURATION_MS,
    AUDIO_SAMPLE_RATE,
    MAX_UTTERANCE_MS,
    MIN_UTTERANCE_MS,
    VAD_PRE_ROLL_MS,
)

CONTINUOUS_WAV = PROJECT_ROOT / "data" / "processed_phone" / "dad_continuous_16k.wav"
AUDIT_CSV = PROJECT_ROOT / "analysis" / "error_audit.csv"
OUTPUT_CSV = PROJECT_ROOT / "analysis" / "vad_calibration.csv"

THRESHOLDS = [450.0, 500.0, 600.0, 700.0, 800.0, 1000.0]
HANGOVERS_MS = [350, 500, 700, 1000]

TIMESTAMP_RE = re.compile(r"\((\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)s\)")


def load_ground_truth_intervals() -> list[tuple[int, int, int]]:
    """Parses per-prompt speech intervals (ms) from the error audit notes."""
    intervals: list[tuple[int, int, int]] = []
    with open(AUDIT_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["engine"] != "vosk":
                continue
            m = TIMESTAMP_RE.search(row["notes"])
            if not m:
                continue  # Prompt 16 excluded; a few notes lack parseable intervals
            start_ms = int(float(m.group(1)) * 1000)
            end_ms = int(float(m.group(2)) * 1000)
            intervals.append((int(row["prompt_id"]), start_ms, end_ms))
    intervals.sort(key=lambda x: x[1])
    return intervals


def segment_continuous(
    samples: np.ndarray,
    threshold: float,
    hangover_ms: int,
) -> list[tuple[float, float, float]]:
    """Runs the production segmenter over the continuous recording.

    Returns list of (start_ms, end_ms, duration_ms) for each emitted utterance.
    """
    block_samples = int(AUDIO_SAMPLE_RATE * AUDIO_BLOCK_DURATION_MS / 1000)
    vad = EnergyVAD(energy_threshold=threshold)
    segmenter = UtteranceSegmenter(
        vad=vad,
        pre_roll_ms=VAD_PRE_ROLL_MS,
        hangover_ms=hangover_ms,
        min_utterance_ms=MIN_UTTERANCE_MS,
        max_utterance_ms=MAX_UTTERANCE_MS,
    )

    segments: list[tuple[float, float, float]] = []
    total_samples = len(samples)
    for i in range(0, total_samples, block_samples):
        chunk = samples[i : i + block_samples]
        start_ms = (i / AUDIO_SAMPLE_RATE) * 1000.0
        frame = AudioFrame(
            data=chunk.tobytes(),
            sample_rate=AUDIO_SAMPLE_RATE,
            channels=1,
            timestamp_ns=int(start_ms * 1_000_000),
            samples_count=len(chunk),
        )
        utterance = segmenter.process_frame(frame)
        if utterance is not None:
            segments.append(
                (
                    utterance.start_timestamp_ns / 1_000_000.0,
                    utterance.end_timestamp_ns / 1_000_000.0,
                    utterance.duration_ms,
                )
            )
    return segments


def score_config(
    segments: list[tuple[float, float, float]],
    intervals: list[tuple[int, int, int]],
) -> dict:
    """Scores segments against ground-truth intervals."""
    clean = split = merged = missed = false_trigger = cap_hits = 0

    for _, gs, ge in intervals:
        overlapping = [s for s in segments if s[0] < ge and s[1] > gs]
        if not overlapping:
            missed += 1
        elif len(overlapping) >= 2:
            split += 1
        else:
            seg = overlapping[0]
            others_touched = sum(
                1 for _, os_, oe in intervals if seg[0] < oe and seg[1] > os_
            )
            if others_touched >= 2:
                merged += 1
            else:
                clean += 1

    for seg in segments:
        if not any(seg[0] < ge and seg[1] > gs for _, gs, ge in intervals):
            false_trigger += 1
        if seg[2] >= MAX_UTTERANCE_MS - 30:  # 30ms = one frame tolerance
            cap_hits += 1

    durations = sorted(s[2] for s in segments)
    median_dur = durations[len(durations) // 2] if durations else 0.0
    return {
        "segments": len(segments),
        "clean": clean,
        "split": split,
        "merged": merged,
        "missed": missed,
        "false_trigger": false_trigger,
        "cap_hits": cap_hits,
        "median_duration_ms": median_dur,
    }


def measure_noise_profile(samples: np.ndarray) -> dict:
    """Reports frame RMS percentiles to characterize the recording's noise floor."""
    block_samples = int(AUDIO_SAMPLE_RATE * AUDIO_BLOCK_DURATION_MS / 1000)
    vad = EnergyVAD(energy_threshold=1.0)
    rms_values = []
    for i in range(0, len(samples), block_samples):
        chunk = samples[i : i + block_samples]
        _, rms, _ = vad.analyze(chunk)
        rms_values.append(rms)
    arr = np.array(rms_values)
    return {
        "p10": float(np.percentile(arr, 10)),
        "p25": float(np.percentile(arr, 25)),
        "p50": float(np.percentile(arr, 50)),
        "p75": float(np.percentile(arr, 75)),
    }


def main() -> None:
    if not CONTINUOUS_WAV.exists():
        print(f"ERROR: continuous recording not found at {CONTINUOUS_WAV}")
        sys.exit(1)

    pcm_bytes, sr, channels = read_wav(str(CONTINUOUS_WAV))
    if sr != AUDIO_SAMPLE_RATE or channels != 1:
        print(f"ERROR: expected {AUDIO_SAMPLE_RATE} Hz mono, got {sr} Hz / {channels} ch")
        sys.exit(1)
    samples = np.frombuffer(pcm_bytes, dtype=np.int16)

    intervals = load_ground_truth_intervals()
    profile = measure_noise_profile(samples)
    duration_s = len(samples) / AUDIO_SAMPLE_RATE

    print("# EXP-006 VAD Calibration Grid — dad_continuous_16k.wav")
    print(f"- Duration: {duration_s:.2f}s | Ground-truth intervals: {len(intervals)}")
    print(
        f"- Frame RMS profile: p10={profile['p10']:.0f}, p25={profile['p25']:.0f}, "
        f"p50={profile['p50']:.0f}, p75={profile['p75']:.0f}"
    )
    print()
    print(
        "| Threshold | Hangover (ms) | Segments | Clean | Split | Merged | Missed | "
        "False triggers | Cap hits | Median seg (ms) |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|")

    rows: list[dict] = []
    for threshold in THRESHOLDS:
        for hangover in HANGOVERS_MS:
            segments = segment_continuous(samples, threshold, hangover)
            s = score_config(segments, intervals)
            rows.append({"threshold": threshold, "hangover_ms": hangover, **s})
            print(
                f"| {threshold:.0f} | {hangover} | {s['segments']} | {s['clean']} | "
                f"{s['split']} | {s['merged']} | {s['missed']} | {s['false_trigger']} | "
                f"{s['cap_hits']} | {s['median_duration_ms']:.0f} |"
            )

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
