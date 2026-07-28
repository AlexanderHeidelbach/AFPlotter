import subprocess
import sys


def test_package_is_importable_without_env_vars():
    """`import afplotter` must succeed with no ALPS_PATH or other env vars set."""
    env = {"PATH": "/usr/bin:/bin"}  # minimal env, deliberately no ALPS_PATH
    result = subprocess.run(
        [sys.executable, "-c", "import afplotter"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
