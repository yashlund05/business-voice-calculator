#!/usr/bin/env python3
"""Dataset Recording Helper CLI Tool for Voice Calculator.

Prompts the user with target numbers or negative phrases from a structured prompt list,
records 16 kHz mono 16-bit PCM WAV audio using MicrophoneCapture, and appends rows to labels.csv.

Follows docs/research.md §3 protocol.

Usage:
    python tools/record_dataset.py [--speaker NAME] [--split dev|calibration|test]
                                   [--session ID] [--output-dir DIR] [--dry-run]
"""

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys
import time
from typing import List, Optional

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from voice_calculator.audio.capture import MicrophoneCapture
from voice_calculator.audio.wavio import write_wav
from voice_calculator.config import (
    AUDIO_SAMPLE_RATE,
    DATA_DIR_PATH,
)


@dataclass(frozen=True)
class PromptItem:
    """Target prompt definition for dataset recording."""

    prompt_text: str
    expected_value: Optional[int]  # None indicates NEGATIVE
    category: str
    notes: str = ""


DEFAULT_PROMPTS: List[PromptItem] = [
    # Units and teens
    PromptItem("zero", 0, "units_teens"),
    PromptItem("one", 1, "units_teens"),
    PromptItem("two", 2, "units_teens"),
    PromptItem("three", 3, "units_teens"),
    PromptItem("four", 4, "units_teens"),
    PromptItem("five", 5, "units_teens"),
    PromptItem("six", 6, "units_teens"),
    PromptItem("seven", 7, "units_teens"),
    PromptItem("eight", 8, "units_teens"),
    PromptItem("nine", 9, "units_teens"),
    PromptItem("ten", 10, "units_teens"),
    PromptItem("eleven", 11, "units_teens"),
    PromptItem("twelve", 12, "units_teens"),
    PromptItem("thirteen", 13, "units_teens"),
    PromptItem("fourteen", 14, "units_teens"),
    PromptItem("fifteen", 15, "units_teens"),
    PromptItem("sixteen", 16, "units_teens"),
    PromptItem("seventeen", 17, "units_teens"),
    PromptItem("eighteen", 18, "units_teens"),
    PromptItem("nineteen", 19, "units_teens"),
    # Tens
    PromptItem("twenty", 20, "tens"),
    PromptItem("thirty", 30, "tens"),
    PromptItem("forty", 40, "tens"),
    PromptItem("fifty", 50, "tens"),
    PromptItem("sixty", 60, "tens"),
    PromptItem("seventy", 70, "tens"),
    PromptItem("eighty", 80, "tens"),
    PromptItem("ninety", 90, "tens"),
    # Confusable pairs (frequent business confusions)
    PromptItem("thirteen", 13, "confusable"),
    PromptItem("thirty", 30, "confusable"),
    PromptItem("fourteen", 14, "confusable"),
    PromptItem("forty", 40, "confusable"),
    PromptItem("fifteen", 15, "confusable"),
    PromptItem("fifty", 50, "confusable"),
    PromptItem("sixteen", 16, "confusable"),
    PromptItem("sixty", 60, "confusable"),
    PromptItem("seventeen", 17, "confusable"),
    PromptItem("seventy", 70, "confusable"),
    PromptItem("eighteen", 18, "confusable"),
    PromptItem("eighty", 80, "confusable"),
    PromptItem("nineteen", 19, "confusable"),
    PromptItem("ninety", 90, "confusable"),
    # Compound numbers 21-99
    PromptItem("twenty five", 25, "compound_tens"),
    PromptItem("forty two", 42, "compound_tens"),
    PromptItem("fifty seven", 57, "compound_tens"),
    PromptItem("ninety nine", 99, "compound_tens"),
    # Hundreds and linguistic variants
    PromptItem("one hundred", 100, "hundreds"),
    PromptItem("a hundred", 100, "hundreds_variant"),
    PromptItem("one hundred five", 105, "hundreds"),
    PromptItem("one hundred and five", 105, "hundreds_and"),
    PromptItem("two hundred fifty", 250, "hundreds"),
    PromptItem("two hundred and fifty", 250, "hundreds_and"),
    PromptItem("seven hundred eighty nine", 789, "hundreds"),
    # Thousands and teen-hundreds
    PromptItem("one thousand", 1000, "thousands"),
    PromptItem("a thousand", 1000, "thousands_variant"),
    PromptItem("one thousand five", 1005, "thousands"),
    PromptItem("one thousand and five", 1005, "thousands_and"),
    PromptItem("one thousand two hundred", 1200, "thousands"),
    PromptItem("one thousand two hundred fifty", 1250, "thousands"),
    PromptItem("one thousand two hundred and fifty", 1250, "thousands_and"),
    PromptItem("fifteen hundred", 1500, "teen_hundreds"),
    PromptItem("fifteen hundred and fifty", 1550, "teen_hundreds_and"),
    PromptItem("two thousand", 2000, "boundary"),
    # Negatives: out of range
    PromptItem("two thousand and one", None, "negative_out_of_range", "out of range"),
    PromptItem("two thousand five hundred", None, "negative_out_of_range", "out of range"),
    PromptItem("five thousand", None, "negative_out_of_range", "out of range"),
    # Negatives: non-numbers / command words (verifies no voice commands)
    PromptItem("undo", None, "negative_non_number", "command word - must be rejected"),
    PromptItem("stop", None, "negative_non_number", "command word - must be rejected"),
    PromptItem("clear", None, "negative_non_number", "command word - must be rejected"),
    PromptItem("reset", None, "negative_non_number", "command word - must be rejected"),
    PromptItem("hello", None, "negative_non_number", "conversational"),
    PromptItem("yes", None, "negative_non_number", "conversational"),
    # Negatives: non-speech / noise
    PromptItem("[Stay silent for 2 seconds]", None, "negative_non_speech", "background silence"),
    PromptItem("[Cough or clear throat]", None, "negative_non_speech", "throat clear noise"),
    PromptItem("[Type on keyboard]", None, "negative_non_speech", "typing noise"),
]


def ensure_labels_csv(csv_path: Path) -> None:
    """Creates labels.csv with proper headers if it does not already exist."""
    if not csv_path.exists():
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "file",
                    "expected_value_or_NEGATIVE",
                    "category",
                    "speaker",
                    "session_id",
                    "split",
                    "notes",
                ]
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Guided audio prompt recorder for Voice Calculator evaluation datasets."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DATA_DIR_PATH / "recordings",
        help="Directory to save WAV files and labels.csv (default: data/recordings)",
    )
    parser.add_argument(
        "--speaker",
        type=str,
        default="developer",
        help="Speaker identifier (e.g. 'father', 'developer') (default: developer)",
    )
    parser.add_argument(
        "--split",
        choices=["dev", "calibration", "test"],
        default="dev",
        help="Dataset split destination (default: dev)",
    )
    parser.add_argument(
        "--session",
        type=str,
        default=datetime.now().strftime("%Y%m%d_%H%M"),
        help="Session identifier (default: current timestamp)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=2.5,
        help="Recording duration in seconds per prompt (default: 2.5s)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Limit number of prompts to record in this session",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate session without accessing microphone or saving files",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir: Path = args.output_dir
    labels_csv = out_dir / "labels.csv"

    print("\n" + "=" * 78)
    print("VOICE CALCULATOR — DATASET RECORDING HELPER")
    print("=" * 78)
    print(f"Destination:  {out_dir}")
    print(f"Labels CSV:   {labels_csv}")
    print(f"Speaker:      {args.speaker}")
    print(f"Split:        {args.split}")
    print(f"Session:      {args.session}")
    print(f"Duration:     {args.duration:.1f}s per utterance")
    if args.dry_run:
        print("[MODE: DRY-RUN — no audio will be recorded]")
    print("-" * 78)

    prompts = DEFAULT_PROMPTS
    if args.count is not None and args.count > 0:
        prompts = prompts[: args.count]

    print(f"Prompts in this session: {len(prompts)}")
    print("Instructions:")
    print("  - Speak clearly in a quiet environment at normal speaking distance.")
    print("  - Press [ENTER] when ready to record each prompt.")
    print("  - Type 'q' and press [ENTER] to exit early.")
    print("=" * 78 + "\n")

    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        ensure_labels_csv(labels_csv)

    recorded_count = 0

    for idx, item in enumerate(prompts, start=1):
        target_display = (
            f"Value: {item.expected_value} | Speak: \"{item.prompt_text}\""
            if item.expected_value is not None
            else f"NEGATIVE | Speak / Act: \"{item.prompt_text}\""
        )
        print(f"[{idx}/{len(prompts)}] Category: {item.category}")
        print(f"   --> {target_display}")
        if item.notes:
            print(f"   Note: {item.notes}")

        if args.dry_run:
            print("   [Dry-run] Simulated prompt.")
            recorded_count += 1
            continue

        user_input = input("   Press [ENTER] to record (or 'q' to quit): ").strip().lower()
        if user_input == "q":
            print("\nRecording stopped by user.")
            break

        # Capture audio
        filename = f"rec_{args.session}_{idx:04d}_{item.category}.wav"
        filepath = out_dir / filename

        print(f"   *** RECORDING ({args.duration:.1f}s)... Speak now! ***")
        cap = MicrophoneCapture()
        cap.start()

        frames_bytes = bytearray()
        start_t = time.monotonic()
        while time.monotonic() - start_t < args.duration:
            frame = cap.read(timeout=0.2)
            if frame is not None:
                frames_bytes.extend(frame.data)

        cap.stop()
        print("   *** DONE RECORDING ***")

        # Save WAV
        write_wav(
            destination=filepath,
            pcm_data=bytes(frames_bytes),
            sample_rate=AUDIO_SAMPLE_RATE,
            channels=1,
            sample_width=2,
        )

        # Append to labels.csv
        with open(labels_csv, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    filename,
                    item.expected_value if item.expected_value is not None else "NEGATIVE",
                    item.category,
                    args.speaker,
                    args.session,
                    args.split,
                    item.notes,
                ]
            )

        recorded_count += 1
        print(f"   Saved -> {filename}\n")

    print("\n" + "=" * 78)
    print(f"Session finished. Recorded {recorded_count} prompt(s).")
    print(f"Labels saved to: {labels_csv}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
