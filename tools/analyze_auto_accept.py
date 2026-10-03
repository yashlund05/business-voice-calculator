"""Phase 5D (EXP-007): auto-accept signal analysis on the Dad benchmark dataset.

Determines whether ANY available signal could support an auto-accept rule that
achieves 0 false additions (research.md §9 policy). Analyzes three candidate
signals on the 61 eligible benchmark utterances:

1. Vosk word-level confidence — probed via ``KaldiRecognizer.SetWords(True)``
   (the production engine returns ``confidence=None``; this reads the raw
   per-word likelihoods the model already computes, for research only).
2. Dual-engine agreement — computed from `analysis/error_audit.csv`
   (Vosk parsed value vs faster-whisper parsed value per prompt).
3. Utterance RMS energy — computed from each benchmark WAV.

A rule is eligible for production only if it yields 0 wrong among auto-accepted
on calibration data AND is later re-evaluated unchanged on a held-out test
split (research.md §9). This script only measures the calibration side.

Offline, deterministic, privacy-safe (no audio leaves the machine; transcripts
are not logged — only numeric signals and match booleans are written).

Usage (repo root):
    python tools/analyze_auto_accept.py
"""

import csv
import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from voice_calculator.audio.vad import EnergyVAD  # noqa: E402
from voice_calculator.audio.wavio import read_wav  # noqa: E402
from voice_calculator.asr.vosk_engine import get_default_number_grammar  # noqa: E402
from voice_calculator.config import AUDIO_SAMPLE_RATE, VOSK_MODEL_PATH  # noqa: E402

AUDIT_CSV = PROJECT_ROOT / "analysis" / "error_audit.csv"
DATASET_DIR = PROJECT_ROOT / "data" / "processed_phone" / "benchmark_dad"
OUTPUT_CSV = PROJECT_ROOT / "analysis" / "auto_accept_signals.csv"


def load_audit_rows() -> dict[int, dict]:
    """Loads the Vosk rows of the error audit keyed by prompt id."""
    rows: dict[int, dict] = {}
    with open(AUDIT_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["engine"] != "vosk":
                continue
            rows[int(row["prompt_id"])] = {
                "intended_value": int(row["intended_value"]),
                "parser_status": row["parser_status"],
                "parsed_value": int(row["parsed_value"]) if row["parsed_value"] else None,
                "correct": row["exact_numeric_match"] == "True",
            }
    return rows


def load_whisper_values() -> dict[int, int | None]:
    """Loads the faster-whisper parsed values keyed by prompt id."""
    values: dict[int, int | None] = {}
    with open(AUDIT_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["engine"] != "faster-whisper-tiny":
                continue
            values[int(row["prompt_id"])] = (
                int(row["parsed_value"]) if row["parsed_value"] else None
            )
    return values


def probe_vosk_word_confidence(
    pcm_bytes: bytes,
    model,
) -> tuple[int, float | None, float | None, str]:
    """Transcribes one utterance with word-level confidences enabled.

    Returns (word_count, mean_word_confidence, result_confidence_field, text).
    """
    import vosk

    rec = vosk.KaldiRecognizer(model, AUDIO_SAMPLE_RATE, json.dumps(get_default_number_grammar()))
    rec.SetWords(True)
    rec.AcceptWaveform(pcm_bytes)
    result = json.loads(rec.FinalResult())

    words = result.get("result", [])
    text = result.get("text", "").strip()
    word_confs = [float(w.get("conf", 0.0)) for w in words]
    mean_conf = float(np.mean(word_confs)) if word_confs else None
    return len(words), mean_conf, result.get("confidence"), text


def rms_of(pcm_bytes: bytes) -> float:
    """Mean frame RMS of a PCM buffer (30 ms frames, matching the segmenter)."""
    vad = EnergyVAD(energy_threshold=1.0)
    block = AUDIO_SAMPLE_RATE * 30 // 1000
    samples = np.frombuffer(pcm_bytes, dtype=np.int16)
    rms_values = [vad.compute_rms(samples[i : i + block]) for i in range(0, len(samples), block)]
    return float(np.mean(rms_values)) if rms_values else 0.0


def distribution(values: list[float]) -> str:
    """Formats a five-number summary for the report table."""
    if not values:
        return "n=0"
    arr = np.array(values)
    return (
        f"n={len(arr)} min={arr.min():.3f} p25={np.percentile(arr, 25):.3f} "
        f"med={np.median(arr):.3f} p75={np.percentile(arr, 75):.3f} max={arr.max():.3f}"
    )


def threshold_scan(
    pairs: list[tuple[float, bool]],
    label: str,
    step: float = 0.05,
    max_value: float = 1.0,
) -> None:
    """Scans `accept if signal >= T` rules; reports coverage and wrong count per T."""
    print(f"\n### Threshold scan — {label} (accept when signal >= T)")
    print("| T >= | Auto-accepted | Correct | Wrong among accepted |")
    print("|---|---|---|---|")
    t = step
    while t <= max_value + 1e-9:
        accepted = [(v, ok) for v, ok in pairs if v >= t]
        wrong = sum(1 for _, ok in accepted if not ok)
        print(f"| {t:.2f} | {len(accepted)} | {len(accepted) - wrong} | {wrong} |")
        t += step


def main() -> None:
    if not DATASET_DIR.exists():
        print(f"ERROR: dataset not found at {DATASET_DIR}")
        sys.exit(1)
    if not VOSK_MODEL_PATH.exists():
        print(f"ERROR: Vosk model not found at {VOSK_MODEL_PATH}")
        sys.exit(1)

    audit = load_audit_rows()
    whisper_values = load_whisper_values()

    # --- Signal 2: dual-engine agreement (no ASR run needed) ---
    print("# EXP-007 Auto-Accept Signal Analysis (N=61 eligible utterances)")
    print()
    print("## Signal: dual-engine agreement (Vosk value == faster-whisper value)")
    both_parsed = 0
    agree = 0
    agree_wrong = 0
    for pid, row in audit.items():
        wv = whisper_values.get(pid)
        if row["parsed_value"] is None or wv is None:
            continue
        both_parsed += 1
        if row["parsed_value"] == wv:
            agree += 1
            if not row["correct"]:
                agree_wrong += 1
    print(
        f"- Utterances where both engines parsed a value: {both_parsed}/61\n"
        f"- Both engines agreed on the same value: {agree}/61\n"
        f"- Wrong among agreed values: {agree_wrong}/{agree}\n"
        f"- Rule-of-three 95% upper bound on wrong among accepted: "
        f"~{3.0 / agree:.1%}" if agree else "- No agreement cases"
    )
    print(
        "- Note: agreement auto-accepts a value only when BOTH engines independently "
        "parse the same integer; disagreements and rejections fall back to confirmation."
    )

    # --- Signals 1 & 3: per-utterance probe with the local Vosk model ---
    import vosk

    vosk.SetLogLevel(-1)
    model = vosk.Model(str(VOSK_MODEL_PATH))

    records: list[dict] = []
    for pid in sorted(audit):
        row = audit[pid]
        wav_path = DATASET_DIR / f"prompt_{pid:03d}.wav"
        if not wav_path.exists():
            continue
        pcm_bytes, sr, ch = read_wav(str(wav_path))
        if sr != AUDIO_SAMPLE_RATE or ch != 1:
            continue
        word_count, mean_conf, result_conf, text = probe_vosk_word_confidence(pcm_bytes, model)
        records.append(
            {
                "prompt_id": pid,
                "intended_value": row["intended_value"],
                "parser_status": row["parser_status"],
                "parsed_value": row["parsed_value"],
                "correct": row["correct"],
                "word_count": word_count,
                "mean_word_conf": mean_conf if mean_conf is not None else "",
                "result_conf_field": result_conf if result_conf is not None else "",
                "rms_mean": round(rms_of(pcm_bytes), 1),
            }
        )

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)

    parsed = [r for r in records if r["parser_status"] == "SUCCESS"]
    correct = [r for r in parsed if r["correct"]]
    wrong = [r for r in parsed if not r["correct"]]

    print()
    print("## Signal: Vosk word-level confidence (SetWords probe)")
    print(f"- FinalResult top-level 'confidence' field across all utterances: "
          f"{sorted({r['result_conf_field'] for r in records if r['result_conf_field'] != ''})} "
          f"(uncalibrated/constant — unusable)")
    print(f"- Correct utterances: {distribution([r['mean_word_conf'] for r in correct if r['mean_word_conf'] != ''])}")
    print(f"- Wrong utterances:   {distribution([r['mean_word_conf'] for r in wrong if r['mean_word_conf'] != ''])}")

    conf_pairs = [
        (float(r["mean_word_conf"]), r["correct"])
        for r in parsed
        if r["mean_word_conf"] != ""
    ]
    threshold_scan(conf_pairs, "Vosk mean word confidence")

    print()
    print("## Signal: utterance RMS energy")
    print(f"- Correct utterances: {distribution([r['rms_mean'] for r in correct])}")
    print(f"- Wrong utterances:   {distribution([r['rms_mean'] for r in wrong])}")
    rms_pairs = [(float(r["rms_mean"]), r["correct"]) for r in parsed]
    threshold_scan(rms_pairs, "mean RMS", step=250.0, max_value=5000.0)

    print(f"\nSaved: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
