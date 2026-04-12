import subprocess, sys

def test_jarvas_help():
    result = subprocess.run(
        [sys.executable, "-m", "jarvas", "--help"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "jarvas" in result.stdout.lower()
