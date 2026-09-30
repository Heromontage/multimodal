from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cardiolens_ml.evaluate import CardioLensEvaluator


def test_evaluator_reports_saved_held_out_results():
    results = CardioLensEvaluator().evaluate_all_targets()

    assert set(results) == {"CAD", "LAD", "LCX", "RCA"}
    assert all(item["source"] == "held_out" for item in results.values())
