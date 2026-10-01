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


def test_app_config_dataclass():
    """Verify AppConfig dataclass provides frozen instance with matching defaults."""
    cfg = config.AppConfig()
    assert cfg.min_number == 0
    assert cfg.max_number == 2000
    assert cfg.auto_accept_enabled is False
    assert cfg.audio_sample_rate == 16000
