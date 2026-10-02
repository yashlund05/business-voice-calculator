"""Single source of truth for constants and tunable configurations.

All tunables, limits, and system constants live here.
No other module should define magic numbers or hardcoded tunable constants.
"""

from pathlib import Path
from dataclasses import dataclass

# Project Root Directory
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent

# --- Number Range (FIXED per prd.md §5, §7) ---
MIN_NUMBER: int = 0
MAX_NUMBER: int = 2000

# --- Audio Capture Defaults (DEFAULT per architecture.md §5) ---
AUDIO_SAMPLE_RATE: int = 16000  # 16 kHz mono
AUDIO_CHANNELS: int = 1
AUDIO_DTYPE: str = "int16"
AUDIO_BLOCK_DURATION_MS: int = 30  # 20-30 ms blocks
AUDIO_QUEUE_MAX_SECONDS: int = 10

# Derived audio sizing
AUDIO_BLOCK_SAMPLES: int = int(AUDIO_SAMPLE_RATE * AUDIO_BLOCK_DURATION_MS / 1000)  # 480 samples @ 16kHz
AUDIO_BLOCK_BYTES: int = AUDIO_BLOCK_SAMPLES * 2  # 960 bytes for 16-bit mono
AUDIO_QUEUE_MAX_BLOCKS: int = int((AUDIO_QUEUE_MAX_SECONDS * 1000) / AUDIO_BLOCK_DURATION_MS)  # ~333 blocks

# --- VAD & Segmentation Defaults ([BENCH] per architecture.md §5) ---
# Note: Initial engineering defaults for quiet room; require calibration on real dataset (docs/research.md).
VAD_ENERGY_THRESHOLD: float = 500.0  # RMS threshold for speech detection on 16-bit PCM
VAD_PRE_ROLL_MS: int = 250
VAD_HANGOVER_MS: int = 700
MIN_UTTERANCE_MS: int = 250
MAX_UTTERANCE_MS: int = 6000

# --- Decision Engine Defaults (DEFAULT per architecture.md §9) ---
# Safe-by-default policy: every parsed value requires confirmation until calibrated.
AUTO_ACCEPT_ENABLED: bool = False
ZERO_REQUIRES_CONFIRMATION: bool = True

# --- Pipeline & Error Recovery Defaults (DEFAULT per architecture.md §6, §12) ---
MAX_CONSECUTIVE_RECOGNITION_ERRORS: int = 5
UI_POLL_INTERVAL_MS: int = 50  # Tkinter after() poll interval

# --- Directory Names & Model Paths (Git-ignored local storage per architecture.md §4, §13) ---
LOG_DIR_PATH: Path = PROJECT_ROOT / "logs"
DATA_DIR_PATH: Path = PROJECT_ROOT / "data"
MODELS_DIR_PATH: Path = PROJECT_ROOT / "models"

import os

VOSK_DEFAULT_MODEL_NAME: str = "vosk-model-small-en-us"
VOSK_MODEL_PATH: Path = Path(os.environ.get("VOICE_CALC_VOSK_MODEL_PATH", MODELS_DIR_PATH / VOSK_DEFAULT_MODEL_NAME))

# --- faster-whisper Candidate ASR Settings (Phase 4A per architecture.md §7, §13) ---
WHISPER_DEFAULT_MODEL_NAME: str = "faster-whisper-base.en"
WHISPER_MODEL_PATH: Path = Path(os.environ.get("VOICE_CALC_WHISPER_MODEL_PATH", MODELS_DIR_PATH / WHISPER_DEFAULT_MODEL_NAME))
WHISPER_DEVICE: str = os.environ.get("VOICE_CALC_WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE: str = os.environ.get("VOICE_CALC_WHISPER_COMPUTE_TYPE", "int8")


@dataclass(frozen=True)
class AppConfig:
    """Immutable application configuration snapshot."""

    min_number: int = MIN_NUMBER
    max_number: int = MAX_NUMBER
    audio_sample_rate: int = AUDIO_SAMPLE_RATE
    audio_channels: int = AUDIO_CHANNELS
    audio_queue_max_seconds: int = AUDIO_QUEUE_MAX_SECONDS
    vad_energy_threshold: float = VAD_ENERGY_THRESHOLD
    vad_pre_roll_ms: int = VAD_PRE_ROLL_MS
    vad_hangover_ms: int = VAD_HANGOVER_MS
    min_utterance_ms: int = MIN_UTTERANCE_MS
    max_utterance_ms: int = MAX_UTTERANCE_MS
    ui_poll_interval_ms: int = UI_POLL_INTERVAL_MS
    auto_accept_enabled: bool = AUTO_ACCEPT_ENABLED
    zero_requires_confirmation: bool = ZERO_REQUIRES_CONFIRMATION
    max_consecutive_errors: int = MAX_CONSECUTIVE_RECOGNITION_ERRORS
    log_dir: Path = LOG_DIR_PATH
    data_dir: Path = DATA_DIR_PATH
    models_dir: Path = MODELS_DIR_PATH
    vosk_model_path: Path = VOSK_MODEL_PATH
    whisper_model_path: Path = WHISPER_MODEL_PATH
    whisper_device: str = WHISPER_DEVICE
    whisper_compute_type: str = WHISPER_COMPUTE_TYPE

