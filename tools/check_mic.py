"""Manual diagnostic tool to list and test physical audio input devices.

Usage:
    python tools/check_mic.py [--test-seconds N]

Does not write audio to disk. Reports detected devices and real-time capture stats.
"""

import argparse
import sys
import time
from pathlib import Path

# Ensure src/ is importable when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

try:
    import sounddevice as sd
    from voice_calculator.audio.capture import MicrophoneCapture, MicNotFound
    from voice_calculator.config import AUDIO_SAMPLE_RATE
except ImportError as e:
    print(f"Import error: {e}. Run inside the virtual environment.")
    sys.exit(1)


def list_devices():
    print("=== Audio Input Devices ===")
    devices = sd.query_devices()
    default_input = sd.default.device[0]
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            is_default = " [DEFAULT]" if i == default_input else ""
            print(f"[{i}] {dev['name']} (inputs: {dev['max_input_channels']}, rate: {dev['default_samplerate']} Hz){is_default}")
    print()


def test_microphone(seconds: float = 2.0):
    print(f"=== Testing Default Microphone Capture ({seconds:.1f}s) ===")
    try:
        with MicrophoneCapture(sample_rate=AUDIO_SAMPLE_RATE) as mic:
            print("Microphone active. Capturing...")
            start_time = time.monotonic()
            frames_read = 0

            while time.monotonic() - start_time < seconds:
                frame = mic.get_frame(timeout=0.1)
                if frame is not None:
                    frames_read += 1

            print(f"Capture successful: {frames_read} frames read ({frames_read * 30} ms), overflows: {mic.overflow_count}")
    except MicNotFound as e:
        print(f"Microphone Not Found: {e}")
    except Exception as e:
        print(f"Capture error: {type(e).__name__}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Voice Calculator Audio Diagnostic Tool")
    parser.add_argument("--test-seconds", type=float, default=2.0, help="Duration to test microphone capture")
    args = parser.parse_args()

    list_devices()
    test_microphone(args.test_seconds)


if __name__ == "__main__":
    main()
