"""Phase 6.3/6.4 (AC-12): verify the packaged Voice Calculator build.

Runs smoke checks against a PyInstaller one-folder distribution:

1. Bundle layout: VoiceCalculator.exe and _internal/ exist.
2. Model bundle: _internal/models/vosk-model-small-en-us contains the required
   model files (final.mdl, conf/model.conf).
3. Native runtime: vosk DLL and PortAudio DLL are present in _internal.
4. Model load from the BUNDLED copy: loads the model via the local venv pointed
   at the bundled directory and transcribes a synthetic tone (proves the
   shipped model files are complete and loadable by the pinned vosk version).
5. GUI launch smoke: starts VoiceCalculator.exe, confirms the process stays
   alive (imports, Tk, and config-path resolution all succeeded), then stops it.

Usage (repo root, after building):
    python tools/verify_package.py --dist dist/VoiceCalculator

Exit code 0 = all checks passed; 1 = any check failed. No network access is
used or required (AC-9 posture).
"""

import argparse
import glob
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

REQUIRED_MODEL_FILES = ["am/final.mdl", "conf/model.conf"]


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify packaged Voice Calculator build")
    parser.add_argument("--dist", default=str(PROJECT_ROOT / "dist" / "VoiceCalculator"))
    parser.add_argument("--launch-seconds", type=float, default=8.0)
    args = parser.parse_args()

    dist = Path(args.dist).resolve()
    exe = dist / "VoiceCalculator.exe"
    internal = dist / "_internal"
    all_ok = True

    # 1. Layout
    all_ok &= check("Bundle layout: exe present", exe.is_file(), str(exe))
    all_ok &= check("Bundle layout: _internal present", internal.is_dir(), str(internal))
    if not exe.is_file():
        return 1

    # 2. Model bundle
    model_dir = internal / "models" / "vosk-model-small-en-us"
    for rel in REQUIRED_MODEL_FILES:
        all_ok &= check(f"Model file: {rel}", (model_dir / rel).is_file())

    # 3. Native runtime DLLs
    vosk_dlls = glob.glob(str(internal / "vosk" / "*.dll")) + glob.glob(str(internal / "vosk.dll"))
    all_ok &= check("vosk native DLL bundled", bool(vosk_dlls), ", ".join(os.path.basename(d) for d in vosk_dlls))
    portaudio = glob.glob(str(internal / "**" / "*portaudio*.dll"), recursive=True) + glob.glob(
        str(internal / "_sounddevice_data" / "**" / "*.dll"), recursive=True
    )
    all_ok &= check("PortAudio DLL bundled", bool(portaudio), ", ".join(os.path.basename(d) for d in portaudio[:3]))

    # 4. Model load from the bundled copy (same files the exe resolves to)
    env = dict(os.environ)
    env["VOICE_CALC_VOSK_MODEL_PATH"] = str(model_dir)
    probe = (
        "import sys; sys.path.insert(0, r'src');\n"
        "import numpy as np\n"
        "from voice_calculator.asr.vosk_engine import VoskEngine\n"
        "e = VoskEngine()\n"
        "e.load()\n"
        "t = np.linspace(0, 0.3, 4800, endpoint=False)\n"
        "pcm = (2000 * np.sin(2 * np.pi * 440 * t)).astype('int16').tobytes()\n"
        "r = e.transcribe(pcm, 16000)\n"
        "print('MODELLOAD', r.status.value)\n"
    )
    try:
        proc = subprocess.run(
            [str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"), "-c", probe],
            env=env, capture_output=True, text=True, timeout=120,
        )
        ok = "MODELLOAD SUCCESS" in proc.stdout or "MODELLOAD NO_SPEECH" in proc.stdout
        all_ok &= check(
            "Model loads from bundled copy", ok,
            (proc.stdout.strip().splitlines() or [proc.stderr.strip()[-200:] or "no output"])[-1],
        )
    except Exception as e:
        all_ok &= check("Model loads from bundled copy", False, str(e))

    # 4b. Frozen-path resolution: simulate sys.frozen (as the exe sees it) and
    # load the engine via the DEFAULT config path — no env override. This
    # proves the packaged exe finds the bundled model without any configuration.
    probe_frozen = (
        "import sys\n"
        "sys.frozen = True\n"
        f"sys._MEIPASS = r'{internal}'\n"
        "sys.path.insert(0, r'src')\n"
        "import numpy as np\n"
        "from voice_calculator.asr.vosk_engine import VoskEngine\n"
        "e = VoskEngine()\n"
        "assert '_internal' in str(e.model_path), e.model_path\n"
        "e.load()\n"
        "t = np.linspace(0, 0.3, 4800, endpoint=False)\n"
        "pcm = (2000 * np.sin(2 * np.pi * 440 * t)).astype('int16').tobytes()\n"
        "r = e.transcribe(pcm, 16000)\n"
        "print('FROZENPATH', r.status.value)\n"
    )
    try:
        proc = subprocess.run(
            [str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"), "-c", probe_frozen],
            capture_output=True, text=True, timeout=120,
        )
        ok = "FROZENPATH SUCCESS" in proc.stdout or "FROZENPATH NO_SPEECH" in proc.stdout
        all_ok &= check(
            "Default (frozen) model path resolves to bundled copy", ok,
            (proc.stdout.strip().splitlines() or [proc.stderr.strip()[-200:] or "no output"])[-1],
        )
    except Exception as e:
        all_ok &= check("Default (frozen) model path resolves to bundled copy", False, str(e))

    # 5. GUI launch smoke: process must stay alive for launch-seconds
    proc = subprocess.Popen([str(exe)], cwd=str(dist))
    try:
        time.sleep(args.launch_seconds)
        alive = proc.poll() is None
        all_ok &= check(
            f"GUI launch smoke (alive after {args.launch_seconds:.0f}s)", alive,
            "process exited early" if not alive else "",
        )
    finally:
        if proc.poll() is None:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/F"], capture_output=True)

    size_mb = sum(f.stat().st_size for f in dist.rglob("*") if f.is_file()) / (1024 * 1024)
    print(f"\nBundle size: {size_mb:.1f} MB ({dist})")
    print("RESULT:", "PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
