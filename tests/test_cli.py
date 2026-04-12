# tests/test_cli.py
import subprocess, sys


def test_jarvas_help():
    result = subprocess.run(
        [sys.executable, "-m", "jarvas", "--help"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "jarvas" in result.stdout.lower()


def test_jarvas_version():
    result = subprocess.run(
        [sys.executable, "-m", "jarvas", "--version"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout
