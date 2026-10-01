"""Minimal smoke test verifying package import and environment sanity."""

import sys
import voice_calculator


def test_package_import_and_version():
    """Verify package can be imported and exposes a valid version string."""
    assert hasattr(voice_calculator, "__version__")
    assert isinstance(voice_calculator.__version__, str)
    assert len(voice_calculator.__version__) > 0


def test_python_version_is_311_or_greater():
    """Verify runtime environment meets the Python >= 3.11 requirement."""
    assert sys.version_info >= (3, 11)
