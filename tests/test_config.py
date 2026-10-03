"""Tests for voice_calculator.config constants and invariants."""

from voice_calculator import config


def test_number_range_invariants():
    """Verify number range matches prd.md §5, §7 (0 to 2000)."""
    assert config.MIN_NUMBER == 0
    assert config.MAX_NUMBER == 2000
    assert config.MIN_NUMBER < config.MAX_NUMBER


def test_audio_defaults():
    """Verify default audio settings match architecture.md §5."""
    assert config.AUDIO_SAMPLE_RATE == 16000
    assert config.AUDIO_CHANNELS == 1
    assert config.AUDIO_DTYPE == "int16"
    assert config.AUDIO_BLOCK_DURATION_MS > 0
    assert config.AUDIO_QUEUE_MAX_SECONDS > 0


def test_safety_defaults():
    """Verify safety defaults (confirm-all, zero requires confirm)."""
    # Auto-accept must be disabled until calibrated in Phase 5
    assert config.AUTO_ACCEPT_ENABLED is False
    assert config.ZERO_REQUIRES_CONFIRMATION is True


def test_vad_defaults():
    """Verify VAD defaults match architecture.md §5."""
    assert config.VAD_ENERGY_THRESHOLD > 0
    assert config.VAD_PRE_ROLL_MS > 0
    assert config.VAD_HANGOVER_MS > 0
    assert config.MIN_UTTERANCE_MS > 0
    assert config.MAX_UTTERANCE_MS > config.MIN_UTTERANCE_MS


def test_app_config_dataclass():
    """Verify AppConfig dataclass provides frozen instance with matching defaults."""
    cfg = config.AppConfig()
    assert cfg.min_number == 0
    assert cfg.max_number == 2000
    assert cfg.auto_accept_enabled is False
    assert cfg.audio_sample_rate == 16000
    assert cfg.vad_energy_threshold == config.VAD_ENERGY_THRESHOLD
    assert cfg.vad_pre_roll_ms == config.VAD_PRE_ROLL_MS
    assert cfg.vad_hangover_ms == config.VAD_HANGOVER_MS
    assert cfg.min_utterance_ms == config.MIN_UTTERANCE_MS
    assert cfg.max_utterance_ms == config.MAX_UTTERANCE_MS


def test_frozen_app_path_resolution(tmp_path):
    """In a PyInstaller build, bundled data resolves to the bundle root and logs to the exe side.

    Regression test for Phase 6.3: config must find models/ inside the onedir
    bundle (_internal, exposed as sys._MEIPASS) and keep logs next to the exe.
    Runs in a fresh interpreter so the frozen environment is simulated before
    the config module is imported.
    """
    import subprocess
    import sys as _sys

    fake_internal = tmp_path / "VoiceCalculator" / "_internal"
    fake_internal.mkdir(parents=True)
    probe = (
        "import sys\n"
        f"sys.frozen = True\n"
        f"sys._MEIPASS = r'{fake_internal}'\n"
        f"sys.executable = r'{tmp_path / 'VoiceCalculator' / 'VoiceCalculator.exe'}'\n"
        "import sys as s; s.path.insert(0, r'src')\n"
        "from voice_calculator import config\n"
        "print('ROOT', config.PROJECT_ROOT)\n"
        "print('LOGS', config.LOG_DIR_PATH)\n"
        "print('MODEL', config.VOSK_MODEL_PATH)\n"
    )
    proc = subprocess.run(
        [_sys.executable, "-c", probe], capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, proc.stderr
    lines = dict(line.split(" ", 1) for line in proc.stdout.strip().splitlines())
    assert lines["ROOT"] == str(fake_internal)
    assert lines["LOGS"] == str(tmp_path / "VoiceCalculator" / "logs")
    assert lines["MODEL"] == str(fake_internal / "models" / "vosk-model-small-en-us")

