"""Verify skeleton package structure and version exports."""

import shellsense


def test_package_version() -> None:
    """Ensure the package version matches expected semantic version format."""
    assert shellsense.__version__ == "0.1.0"
