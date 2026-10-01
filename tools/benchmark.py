#!/usr/bin/env python3
"""ASR Benchmark CLI Tool for Voice Calculator.

Evaluates an ASR engine against a labeled dataset of WAV audio files.
Computes Exact Integer Accuracy (EIA), False Addition Rate, Latency stats,
and category breakdowns per docs/research.md §4.

Usage:
    python tools/benchmark.py [--dataset-dir DIR] [--labels-csv FILE] [--engine ENGINE]
                              [--model-path PATH] [--output-csv OUT] [--split SPLIT]
"""

import argparse
from pathlib import Path
import sys

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from voice_calculator.asr.base import ASREngine, FakeEngine, ModelMissingError
from voice_calculator.asr.vosk_engine import VoskEngine
from voice_calculator.benchmark import (
    export_results_csv,
    format_benchmark_report,
    load_labels_csv,
    run_benchmark,
)
from voice_calculator.config import DATA_DIR_PATH, VOSK_MODEL_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run offline ASR benchmark on labeled WAV datasets."
    )
    default_dataset_dir = DATA_DIR_PATH / "eval" if (DATA_DIR_PATH / "eval").exists() else DATA_DIR_PATH / "recordings"
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=default_dataset_dir,
        help="Directory containing WAV files and default labels.csv (default: data/eval or data/recordings)",
    )
    parser.add_argument(
        "--labels-csv",
        type=Path,
        default=None,
        help="Path to labels.csv (defaults to <dataset-dir>/labels.csv)",
    )
    parser.add_argument(
        "--engine",
        choices=["vosk", "fake"],
        default="vosk",
        help="ASR engine backend to evaluate (default: vosk)",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=VOSK_MODEL_PATH,
        help="Path to Vosk model directory (default: models/vosk-model-small-en-us)",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=None,
        help="Optional path to write detailed per-utterance results CSV (e.g. data/results/eval_vosk.csv)",
    )
    parser.add_argument(
        "--split",
        type=str,
        default=None,
        help="Optional split filter (e.g. 'dev', 'calibration', 'test')",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Optional category filter (e.g. 'canonical', 'confusable', 'negative_non_speech')",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_dir: Path = args.dataset_dir
    labels_path: Path = args.labels_csv or (dataset_dir / "labels.csv")

    print("\n" + "=" * 78)
    print("VOICE CALCULATOR — ASR BENCHMARK RUNNER")
    print("=" * 78)
    print(f"Dataset directory: {dataset_dir}")
    print(f"Labels CSV path:   {labels_path}")
    print(f"Engine requested:  {args.engine}")
    if args.engine == "vosk":
        print(f"Vosk model path:   {args.model_path}")
    if args.split:
        print(f"Split filter:      {args.split}")
    if args.category:
        print(f"Category filter:   {args.category}")
    print("-" * 78)

    # 1. Check labels CSV existence
    if not labels_path.is_file():
        print(f"\n[INFO] Labels file not found at: {labels_path}")
        print("\nTo prepare or record evaluation data:")
        print("  1. Use 'python tools/record_dataset.py' to record guided audio prompts.")
        print("  2. Or place labeled WAV recordings in 'data/recordings/' with a 'labels.csv' file.")
        print("  Columns: file, expected_value_or_NEGATIVE, category, speaker, session_id, split, notes")
        print("\nBenchmark cannot proceed without labeled dataset.")
        return 0

    # 2. Load and filter labels
    try:
        all_labels = load_labels_csv(labels_path)
    except Exception as e:
        print(f"\n[ERROR] Failed to load labels CSV: {e}")
        return 1

    filtered_labels = all_labels
    if args.split:
        filtered_labels = [l for l in filtered_labels if l.split.lower() == args.split.lower()]
    if args.category:
        filtered_labels = [l for l in filtered_labels if l.category.lower() == args.category.lower()]

    if not filtered_labels:
        print(f"\n[WARNING] No labels found matching filters (total in CSV: {len(all_labels)}).")
        return 0

    print(f"Loaded {len(filtered_labels)} sample(s) for evaluation (out of {len(all_labels)} total).")

    # 3. Instantiate Engine
    engine: ASREngine
    if args.engine == "vosk":
        try:
            engine = VoskEngine(model_path=args.model_path)
            print(f"Initializing Vosk model from: {args.model_path} ...")
            engine.load()
            print("Vosk model loaded successfully.")
        except ModelMissingError:
            print(f"\n[ERROR] Vosk model directory missing: {args.model_path}")
            print("\nPlease download the official lightweight model and extract it:")
            print("  URL: https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip")
            print(f"  Target directory: {args.model_path}")
            return 1
        except Exception as e:
            print(f"\n[ERROR] Failed to load Vosk engine: {e}")
            return 1
    elif args.engine == "fake":
        engine = FakeEngine(name="fake_benchmark_engine", default_text="one hundred")
        engine.load()
    else:
        print(f"\n[ERROR] Unsupported engine: {args.engine}")
        return 1

    # 4. Run Benchmark
    print("\nRunning evaluation...")
    results, metrics = run_benchmark(
        engine=engine,
        dataset_dir=dataset_dir,
        labels=filtered_labels,
    )

    # 5. Output Report
    report = format_benchmark_report(
        metrics=metrics,
        engine_name=engine.name,
        split_filter=args.split,
    )
    print("\n" + report)

    # 6. Export results CSV if requested
    if args.output_csv:
        try:
            export_results_csv(results, args.output_csv)
            print(f"\nDetailed per-utterance results exported to: {args.output_csv}")
        except Exception as e:
            print(f"\n[ERROR] Failed to export results CSV: {e}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
