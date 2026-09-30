"""Publish the held-out metrics saved during training.

The fitted artifacts are refit on all patients, so evaluating them on the
training CSV would overstate their performance. Only the untouched test split
from training is used in the public report.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict

import yaml


class CardioLensEvaluator:
    def __init__(self, artifacts_dir: str = None, config_path: str = None):
        ml_root = Path(__file__).resolve().parents[2]
        self.artifacts_dir = Path(artifacts_dir or os.environ.get("ARTIFACTS_DIR", ml_root / "artifacts"))
        config = Path(config_path) if config_path else ml_root / "config.yaml"
        with open(config, encoding="utf-8") as handle:
            self.targets = yaml.safe_load(handle)["targets"]

    def evaluate_model(self, target: str) -> Dict[str, Any]:
        path = self.artifacts_dir / f"{target}_metrics.json"
        with open(path, encoding="utf-8") as handle:
            result = json.load(handle)["metrics"]
        if result.get("source") != "held_out":
            raise ValueError(f"{target} has no held-out evaluation")
        return result

    def evaluate_all_targets(self) -> Dict[str, Any]:
        return {target: self.evaluate_model(target) for target in self.targets}

    def save_evaluation_results(self, results: Dict[str, Any]) -> None:
        path = self.artifacts_dir / "metrics.json"
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"evaluation": results}, handle, indent=2)

    def generate_report(self, results: Dict[str, Any]) -> str:
        lines = ["# CardioLens Held-Out Evaluation", "", "Results use an untouched 20% stratified test split.", ""]
        for target in self.targets:
            metrics = results[target]
            lines.extend([
                f"## {target}",
                f"- Accuracy: {metrics['accuracy']:.4f}",
                f"- Precision: {metrics['precision']:.4f}",
                f"- Recall: {metrics['recall']:.4f}",
                f"- F1: {metrics['f1']:.4f}",
                f"- ROC-AUC: {metrics['roc_auc']:.4f}",
                f"- PR-AUC: {metrics['pr_auc']:.4f}",
                f"- Brier score: {metrics['brier_score']:.4f}",
                f"- Training-fold ROC-AUC: {metrics['cv_roc_auc_mean']:.4f} ± {metrics['cv_roc_auc_std']:.4f}",
                "",
            ])
        return "\n".join(lines)


def main() -> None:
    evaluator = CardioLensEvaluator()
    results = evaluator.evaluate_all_targets()
    evaluator.save_evaluation_results(results)
    report = evaluator.generate_report(results)
    (evaluator.artifacts_dir / "evaluation_report.txt").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
