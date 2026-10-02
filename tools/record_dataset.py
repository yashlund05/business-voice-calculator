#!/usr/bin/env python3
"""Dataset Recording Helper CLI Tool for Voice Calculator.

Prompts the user with target numbers or negative phrases from a structured prompt list,
records 16 kHz mono 16-bit PCM WAV audio using MicrophoneCapture, and appends rows to labels.csv.

Follows docs/research.md §3 protocol.

Usage:
    python tools/record_dataset.py [--speaker NAME] [--split dev|calibration|test]
                                   [--session ID] [--output-dir DIR] [--category CAT]
                                   [--device DEV] [--duration SEC] [--dry-run]
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
    # 1. Units and teens (0-19)
    PromptItem("zero", 0, "units_teens", "canonical unit"),
    PromptItem("one", 1, "units_teens", "canonical unit"),
    PromptItem("two", 2, "units_teens", "canonical unit"),
    PromptItem("three", 3, "units_teens", "canonical unit"),
    PromptItem("four", 4, "units_teens", "canonical unit"),
    PromptItem("five", 5, "units_teens", "canonical unit"),
    PromptItem("six", 6, "units_teens", "canonical unit"),
    PromptItem("seven", 7, "units_teens", "canonical unit"),
    PromptItem("eight", 8, "units_teens", "canonical unit"),
    PromptItem("nine", 9, "units_teens", "canonical unit"),
    PromptItem("ten", 10, "units_teens", "canonical teen"),
    PromptItem("eleven", 11, "units_teens", "canonical teen"),
    PromptItem("twelve", 12, "units_teens", "canonical teen"),
    PromptItem("thirteen", 13, "units_teens", "canonical teen"),
    PromptItem("fourteen", 14, "units_teens", "canonical teen"),
    PromptItem("fifteen", 15, "units_teens", "canonical teen"),
    PromptItem("sixteen", 16, "units_teens", "canonical teen"),
    PromptItem("seventeen", 17, "units_teens", "canonical teen"),
    PromptItem("eighteen", 18, "units_teens", "canonical teen"),
    PromptItem("nineteen", 19, "units_teens", "canonical teen"),

    # 2. Tens (20-90)
    PromptItem("twenty", 20, "tens", "canonical ten"),
    PromptItem("thirty", 30, "tens", "canonical ten"),
    PromptItem("forty", 40, "tens", "canonical ten"),
    PromptItem("fifty", 50, "tens", "canonical ten"),
    PromptItem("sixty", 60, "tens", "canonical ten"),
    PromptItem("seventy", 70, "tens", "canonical ten"),
    PromptItem("eighty", 80, "tens", "canonical ten"),
    PromptItem("ninety", 90, "tens", "canonical ten"),

    # 3. Confusable pairs (frequent business confusions)
    PromptItem("thirteen", 13, "confusable", "confusable with 30"),
    PromptItem("thirty", 30, "confusable", "confusable with 13"),
    PromptItem("fourteen", 14, "confusable", "confusable with 40"),
    PromptItem("forty", 40, "confusable", "confusable with 14"),
    PromptItem("fifteen", 15, "confusable", "confusable with 50"),
    PromptItem("fifty", 50, "confusable", "confusable with 15"),
    PromptItem("sixteen", 16, "confusable", "confusable with 60"),
    PromptItem("sixty", 60, "confusable", "confusable with 16"),
    PromptItem("seventeen", 17, "confusable", "confusable with 70"),
    PromptItem("seventy", 70, "confusable", "confusable with 17"),
    PromptItem("eighteen", 18, "confusable", "confusable with 80"),
    PromptItem("eighty", 80, "confusable", "confusable with 18"),
    PromptItem("nineteen", 19, "confusable", "confusable with 90"),
    PromptItem("ninety", 90, "confusable", "confusable with 19"),

    # 4. Compound numbers 21-99
    PromptItem("twenty one", 21, "compound_tens", "compound 21"),
    PromptItem("thirty five", 35, "compound_tens", "compound 35"),
    PromptItem("forty two", 42, "compound_tens", "compound 42"),
    PromptItem("forty seven", 47, "compound_tens", "compound 47"),
    PromptItem("fifty seven", 57, "compound_tens", "compound 57"),
    PromptItem("ninety nine", 99, "compound_tens", "compound 99"),

    # 5. Hundreds and linguistic variants
    PromptItem("one hundred", 100, "hundreds", "canonical 100"),
    PromptItem("a hundred", 100, "hundreds_variant", "variant with 'a'"),
    PromptItem("one hundred five", 105, "hundreds", "canonical 105"),
    PromptItem("one hundred and five", 105, "hundreds_and", "105 with 'and'"),
    PromptItem("two hundred forty", 240, "hundreds", "canonical 240"),
    PromptItem("two hundred and forty", 240, "hundreds_and", "240 with 'and'"),
    PromptItem("two hundred fifty", 250, "hundreds", "canonical 250"),
    PromptItem("two hundred and fifty", 250, "hundreds_and", "250 with 'and'"),
    PromptItem("five hundred ninety nine", 599, "hundreds", "canonical 599"),
    PromptItem("five hundred and ninety nine", 599, "hundreds_and", "599 with 'and'"),
    PromptItem("seven hundred eighty nine", 789, "hundreds", "canonical 789"),
    PromptItem("nine hundred ninety nine", 999, "hundreds", "canonical 999"),
    PromptItem("nine hundred and ninety nine", 999, "hundreds_and", "999 with 'and'"),

    # 6. Thousands, teen-hundreds, and boundary values
    PromptItem("one thousand", 1000, "thousands", "canonical 1000"),
    PromptItem("a thousand", 1000, "thousands_variant", "variant with 'a'"),
    PromptItem("one thousand five", 1005, "thousands", "canonical 1005"),
    PromptItem("one thousand and five", 1005, "thousands_and", "1005 with 'and'"),
    PromptItem("one thousand two hundred", 1200, "thousands", "canonical 1200"),
    PromptItem("one thousand two hundred five", 1205, "thousands", "canonical 1205"),
    PromptItem("one thousand two hundred and five", 1205, "thousands_and", "1205 with 'and'"),
    PromptItem("one thousand two hundred fifty", 1250, "thousands", "canonical 1250"),
    PromptItem("one thousand two hundred and fifty", 1250, "thousands_and", "1250 with 'and'"),
    PromptItem("fifteen hundred", 1500, "teen_hundreds", "teen-hundred 1500"),
    PromptItem("fifteen hundred and fifty", 1550, "teen_hundreds_and", "1550 with 'and'"),
    PromptItem("nineteen hundred", 1900, "teen_hundreds", "teen-hundred 1900"),
    PromptItem("nineteen hundred five", 1905, "teen_hundreds", "1905 without 'and'"),
    PromptItem("nineteen hundred and five", 1905, "teen_hundreds_and", "1905 with 'and'"),
    PromptItem("two thousand", 2000, "boundary", "upper boundary 2000"),

    # 7. Negatives: out of range (> 2000)
    PromptItem("two thousand and one", None, "negative_out_of_range", "out of range 2001"),
    PromptItem("two thousand five hundred", None, "negative_out_of_range", "out of range 2500"),
    PromptItem("five thousand", None, "negative_out_of_range", "out of range 5000"),

    # 7. Negatives: command-like words (verifies no voice commands)
    PromptItem("undo", None, "negative_non_number", "command word - must be rejected"),
    PromptItem("stop", None, "negative_non_number", "command word - must be rejected"),
    PromptItem("clear", None, "negative_non_number", "command word - must be rejected"),
    PromptItem("reset", None, "negative_non_number", "command word - must be rejected"),

    # 7. Negatives: conversational / irrelevant speech
    PromptItem("hello", None, "negative_non_number", "conversational"),
    PromptItem("yes", None, "negative_non_number", "conversational"),
    PromptItem("okay", None, "negative_non_number", "conversational"),
    PromptItem("thank you", None, "negative_non_number", "conversational"),

    # 7. Negatives: malformed number phrases
    PromptItem("ten hundred", None, "negative_malformed", "invalid scale multiplier"),
    PromptItem("twenty twenty", None, "negative_malformed", "adjacent tens without scale"),
    PromptItem("one twenty", None, "negative_malformed", "collated units/tens"),
    PromptItem("forty and five", None, "negative_malformed", "invalid 'and' between tens and units"),

    # 7. Negatives: non-speech / noise / silence
    PromptItem("[Stay silent for 2 seconds]", None, "negative_non_speech", "background silence"),
    PromptItem("[Cough or clear throat]", None, "negative_non_speech", "throat clear noise"),
    PromptItem("[Type on keyboard]", None, "negative_non_speech", "keyboard typing noise"),
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
        "--category",
        type=str,
        default=None,
        help="Filter prompts to a specific category (e.g. 'units_teens', 'tens', 'confusable', 'hundreds', 'thousands', 'negative_non_number', 'negative_non_speech')",
    )
    parser.add_argument(
        "--device",
        type=int,
        default=None,
        help="Optional input audio device index",
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
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List available prompt categories and counts, then exit",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.list_categories:
        counts = {}
        for p in DEFAULT_PROMPTS:
            counts[p.category] = counts.get(p.category, 0) + 1
        print("\nAvailable prompt categories:")
        for cat, count in sorted(counts.items()):
            print(f"  - {cat:<24} ({count} prompts)")
        print(f"Total default prompts: {len(DEFAULT_PROMPTS)}")
        return 0

    out_dir: Path = args.output_dir
    labels_csv = out_dir / "labels.csv"

    prompts = DEFAULT_PROMPTS
    if args.category:
        prompts = [p for p in prompts if p.category.lower() == args.category.lower()]
        if not prompts:
            print(f"[ERROR] No prompts found for category '{args.category}'. Use --list-categories to view options.", file=sys.stderr)
            return 1

    if args.count is not None and args.count > 0:
        prompts = prompts[: args.count]

    print("\n" + "=" * 78)
    print("VOICE CALCULATOR — DATASET RECORDING HELPER")
    print("=" * 78)
    print(f"Destination:  {out_dir}")
    print(f"Labels CSV:   {labels_csv}")
    print(f"Speaker:      {args.speaker}")
    print(f"Split:        {args.split}")
    print(f"Session:      {args.session}")
    print(f"Duration:     {args.duration:.1f}s per utterance")
    if args.category:
        print(f"Category:     {args.category}")
    if args.device is not None:
        print(f"Audio Device: {args.device}")
    if args.dry_run:
        print("[MODE: DRY-RUN — no audio will be recorded]")
    print("-" * 78)

    print(f"Prompts in this session: {len(prompts)}")
    print("Controls:")
    print("  - [ENTER]  : Record prompt")
    print("  - 's'      : Skip current prompt")
    print("  - 'q'      : Quit recording session")
    print("=" * 78 + "\n")

    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        ensure_labels_csv(labels_csv)

    recorded_count = 0
    idx = 0

    while idx < len(prompts):
        item = prompts[idx]
        target_display = (
            f"Value: {item.expected_value} | Speak: \"{item.prompt_text}\""
            if item.expected_value is not None
            else f"NEGATIVE | Speak / Act: \"{item.prompt_text}\""
        )
        print(f"[{idx + 1}/{len(prompts)}] Category: {item.category}")
        print(f"   --> {target_display}")
        if item.notes:
            print(f"   Note: {item.notes}")

        if args.dry_run:
            print("   [Dry-run] Simulated prompt.")
            recorded_count += 1
            idx += 1
            continue

        user_input = input("   Press [ENTER] to record (or 's' to skip, 'q' to quit): ").strip().lower()
        if user_input == "q":
            print("\nRecording stopped by user.")
            break
        elif user_input == "s":
            print("   [Skipped]\n")
            idx += 1
            continue

        # Capture audio
        filename = f"rec_{args.session}_{idx + 1:04d}_{item.category}.wav"
        filepath = out_dir / filename

        print(f"   *** RECORDING ({args.duration:.1f}s)... Speak clearly! ***")
        cap = MicrophoneCapture(device_index=args.device)
        cap.start()

        frames_bytes = bytearray()
        start_t = time.monotonic()
        while time.monotonic() - start_t < args.duration:
            frame = cap.get_frame(timeout=0.2)
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
        print(f"   Saved -> {filename}")

        # Post-recording confirmation option
        post_input = input("   Press [ENTER] for next, or 'r' to re-record this prompt: ").strip().lower()
        if post_input == "r":
            print("   Re-recording current prompt...\n")
            continue

        print()
        idx += 1

    print("\n" + "=" * 78)
    print(f"Session finished. Recorded {recorded_count} prompt(s).")
    print(f"Labels saved to: {labels_csv}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
