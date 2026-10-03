# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — Voice Calculator one-folder Windows build (Phase 6.3, P9).

Build from the repository root:
    pyinstaller --noconfirm --distpath dist --workpath build build_spec/voice_calculator.spec

Output: dist/VoiceCalculator/VoiceCalculator.exe with _internal/ containing the
bundled Vosk model (models/vosk-model-small-en-us), the vosk native DLL, and
PortAudio. Fully offline: nothing is downloaded at build or run time.
faster-whisper is intentionally excluded (ADR-001: not the default engine).

Path resolution: config.py derives PROJECT_ROOT from config.py's own location;
in the onedir layout that lands on _internal/, so the model must be collected
to "models/..." (relative to _internal) — which this spec does.
"""

import glob
import importlib.util
import os

from PyInstaller.utils.hooks import collect_all

PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ENTRY = os.path.join(PROJECT_ROOT, "src", "voice_calculator", "__main__.py")
MODEL_DIR = os.path.join(PROJECT_ROOT, "models", "vosk-model-small-en-us")

# vosk: hidden import + package data + native DLL placed INSIDE the vosk
# package directory (vosk/__init__.py loads the DLL relative to __file__).
vosk_datas, vosk_binaries, vosk_hiddenimports = collect_all("vosk")
try:
    vosk_pkg_dir = os.path.dirname(importlib.util.find_spec("vosk").origin)
    for dll in glob.glob(os.path.join(vosk_pkg_dir, "*.dll")):
        vosk_datas.append((dll, "vosk"))
except Exception:
    pass

a = Analysis(
    [ENTRY],
    pathex=[os.path.join(PROJECT_ROOT, "src")],
    binaries=vosk_binaries,
    datas=[(MODEL_DIR, os.path.join("models", "vosk-model-small-en-us"))] + vosk_datas,
    hiddenimports=["vosk", "sounddevice"] + vosk_hiddenimports,
    excludes=["faster_whisper", "ctranslate2", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VoiceCalculator",
    debug=False,
    console=False,  # GUI application: no console window
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,  # UPX triggers AV false positives and corrupts some native DLLs
    name="VoiceCalculator",
)
