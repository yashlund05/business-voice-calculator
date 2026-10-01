#!/usr/bin/env python3
"""Transcribe CLI Tool for Voice Calculator.

Transcribes one WAV file or a folder of WAV files offline using an ASREngine
and runs the recognized transcript through the deterministic number parser.

Usage:
    python tools/transcribe.py <path-to-wav-or-dir> [--engine ENGINE] [--model-path PATH]
"""

import argparse
from pathlib import Path
import sys
from typing import List

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from voice_calculator.asr.base import ASREngine, ASRStatus, FakeEngine, ModelMissingError
from voice_calculator.asr.vosk_engine import VoskEngine
from voice_calculator.audio.wavio import WavFormatError, read_wav
from voice_calculator.config import VOSK_MODEL_PATH
from voice_calculator.numparse import ParseStatus, parse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transcribe WAV file(s) and parse spoken numbers offline."
    )
    parser.add_argument(
        "target",
        type=Path,
        help="Path to a single 16 kHz mono WAV file or directory containing WAV files",
    )
    parser.add_argument(
        "--engine",
        choices=["vosk", "fake"],
        default="vosk",
        help="ASR engine backend (default: vosk)",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=VOSK_MODEL_PATH,
        help="Path to Vosk model directory (default: models/vosk-model-small-en-us)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target_path: Path = args.target

    if not target_path.exists():
        print(f"[ERROR] Target path not found: {target_path}", file=sys.stderr)
        return 1

    # Collect WAV files
    wav_files: List[Path] = []
    if target_path.is_file():
        if target_path.suffix.lower() != ".wav":
            print(f"[ERROR] File is not a .wav file: {target_path}", file=sys.stderr)
            return 1
        wav_files.append(target_path)
    elif target_path.is_dir():
        wav_files = sorted(list(target_path.glob("*.wav")))
        if not wav_files:
            print(f"[WARNING] No .wav files found in directory: {target_path}")
            return 0

    # Initialize Engine
    engine: ASREngine
    if args.engine == "vosk":
        try:
            engine = VoskEngine(model_path=args.model_path)
            engine.load()
        except ModelMissingError:
            print(f"\n[ERROR] Vosk model directory missing: {args.model_path}", file=sys.stderr)
            print("Please download and place the model in the models/ directory.", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"\n[ERROR] Failed to load Vosk model: {e}", file=sys.stderr)
            return 1
    elif args.engine == "fake":
        engine = FakeEngine(name="fake_engine", default_text="one hundred")
        engine.load()
    else:
        print(f"[ERROR] Unsupported engine: {args.engine}", file=sys.stderr)
        return 1

    print(f"\nProcessing {len(wav_files)} file(s) with engine '{engine.name}'...")
    print("=" * 88)
    print(f"{'Filename':<30} {'Status':<10} {'Recognized Text':<22} {'Parsed':<10} {'ms':>6}")
    print("-" * 88)

    for wav_path in wav_files:
        try:
            pcm_bytes, sr, ch = read_wav(wav_path)
        except WavFormatError as e:
            print(f"{wav_path.name:<30} {'WAV_ERROR':<10} {'[Malformed WAV]':<22} {'REJECT':<10} {0.0:>6.1f}")
            continue
        except Exception as e:
            print(f"{wav_path.name:<30} {'IO_ERROR':<10} {str(e)[:20]:<22} {'REJECT':<10} {0.0:>6.1f}")
            continue

        asr_res = engine.transcribe(pcm_bytes)
        if asr_res.status == ASRStatus.SUCCESS:
            parse_res = parse(asr_res.text)
            if parse_res.status == ParseStatus.SUCCESS:
                parsed_str = f"{parse_res.value}"
            else:
                parsed_str = f"REJ({parse_res.reason.value if parse_res.reason else 'ERR'})"
            text_disp = f"\"{asr_res.text}\"" if asr_res.text else "(empty)"
            print(f"{wav_path.name:<30} {'SUCCESS':<10} {text_disp:<22} {parsed_str:<10} {asr_res.elapsed_ms:>6.1f}")
        elif asr_res.status == ASRStatus.NO_SPEECH:
            print(f"{wav_path.name:<30} {'NO_SPEECH':<10} {'(silence)':<22} {'REJ(EMPTY)':<10} {asr_res.elapsed_ms:>6.1f}")
        else:
            print(f"{wav_path.name:<30} {'ERROR':<10} {str(asr_res.error_message or '')[:20]:<22} {'REJECT':<10} {asr_res.elapsed_ms:>6.1f}")

    print("=" * 88)
    return 0


if __name__ == "__main__":
    sys.exit(main())
