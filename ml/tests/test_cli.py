from pathlib import Path
import os
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_data_and_pipeline_module_smoke_commands():
    env = {**os.environ, "PYTHONPATH": str(ROOT / "ml" / "src")}
    for module in ("cardiolens_ml.data", "cardiolens_ml.pipeline"):
        result = subprocess.run(
            [sys.executable, "-m", module], cwd=ROOT,
            env=env, capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stderr
