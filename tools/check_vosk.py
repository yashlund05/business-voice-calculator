"""Manual diagnostic tool to verify local Vosk model installation and transcription.

Usage:
    python tools/check_vosk.py [--wav path/to/file.wav] [--model-path path/to/model]

Never downloads models automatically. Reports local model status and tests offline transcription.
"""

import argparse
from pathlib import Path
import sys
import time

# Ensure src/ is importable when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

try:
    from voice_calculator.asr.vosk_engine import VoskEngine
    from voice_calculator.audio.wavio import read_wav
    from voice_calculator.config import VOSK_MODEL_PATH
    from voice_calculator.numparse import parse
except ImportError as e:
    print(f"Import error: {e}. Run inside the virtual environment.")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Voice Calculator Vosk Model Diagnostic Tool")
    parser.add_argument("--model-path", type=str, default=str(VOSK_MODEL_PATH), help="Path to local Vosk model directory")
    parser.add_argument("--wav", type=str, default=None, help="Optional WAV file (16kHz mono int16) to transcribe")
    args = parser.parse_args()

    model_dir = Path(args.model_path)
    print(f"=== Vosk Model Diagnostic ===")
    print(f"Target model directory: {model_dir.resolve()}")

    if not model_dir.exists() or not model_dir.is_dir():
        print(f"[STATUS] Model directory not found.")
        print(f"[ACTION REQUIRED] To use real Vosk ASR:")
        print(f"  1. Download vosk-model-small-en-us-0.15 (or small-en-us) manually.")
        print(f"  2. Extract it into: {model_dir.resolve()}")
        print(f"  3. Re-run this diagnostic.")
        return 0

    print("[STATUS] Model directory found. Loading model into memory...")
    start_load = time.monotonic()
    engine = VoskEngine(model_path=model_dir)

    try:
        engine.load()
        load_ms = (time.monotonic() - start_load) * 1000.0
        print(f"[SUCCESS] Model loaded successfully in {load_ms:.1f} ms.")
    except Exception as e:
        print(f"[ERROR] Failed to load model: {type(e).__name__}: {e}")
        return 1

    # Transcription test
    if args.wav:
        wav_path = Path(args.wav)
        print(f"\nTranscribing file: {wav_path}...")
        try:
            pcm_data, sample_rate, channels = read_wav(wav_path)
            print(f"Audio loaded: {len(pcm_data)} bytes ({len(pcm_data)/32000:.2f}s, {sample_rate} Hz, {channels} ch)")
            res = engine.transcribe(pcm_data, sample_rate=sample_rate)
        except Exception as e:
            print(f"[ERROR] Failed to read/transcribe WAV: {e}")
            return 1
    else:
        print("\nTranscribing 1.0s synthetic silence test buffer...")
        silence_pcm = b"\x00" * 32000
        res = engine.transcribe(silence_pcm)

    print(f"ASR Status:     {res.status.value}")
    print(f"Recognized Text: '{res.text}'")
    print(f"Inference Time:  {res.elapsed_ms:.1f} ms")

    if res.text:
        parse_res = parse(res.text)
        print(f"Parser Result:   Status={parse_res.status.value}, Value={parse_res.value}, Reason={parse_res.reason}")
    else:
        print("Parser Result:   (No speech recognized)")

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
