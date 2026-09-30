"""
Model training script for CardioLens
"""
import pandas as pd
import numpy as np
import yaml
import json
import joblib
from pathlib import Path
from typing import Dict, Any, Tuple
import os
import hashlib
import optuna
from sklearn.model_selection import StratifiedKFold, RepeatedStratifiedKFold, cross_val_score, train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, average_precision_score, brier_score_loss
from sklearn.calibration import CalibratedClassifierCV
import shap

from .data import CardioLensDataProcessor
from .pipeline import create_model_pipeline, get_model_params


class CardioLensTrainer:
    """Train and evaluate CardioLens models"""

    def __init__(self, config_path: str = None):
        ml_root = Path(__file__).resolve().parents[2]
        project_root = ml_root.parent

        if config_path is None:
            config_path = str(ml_root / "config.yaml")

        self.processor = CardioLensDataProcessor(config_path)
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.targets = self.config['targets']
        self.random_seed = self.config['random_seeds']['global']
        
        # Save artifacts inside ml/artifacts by default
        self.artifacts_dir = Path(os.environ.get("ARTIFACTS_DIR", ml_root / "artifacts"))
        self.artifacts_dir.mkdir(exist_ok=True, parents=True)

        # Create model-specific directories
        (self.artifacts_dir / "models").mkdir(exist_ok=True, parents=True)

    def load_and_prepare_data(self) -> pd.DataFrame:
        """Load and clean the data"""
        ml_root = Path(__file__).resolve().parents[2]
        project_root = ml_root.parent
        data_path = project_root / self.config.get('data_file', 'file.csv')
        if not data_path.exists():
            data_path = project_root / "data" / "raw" / "z_alizadeh_sani_extension.csv"

        df = self.processor.load_data(str(data_path))
        df_clean = self.processor.clean_data(df)
        return df_clean

    def objective(self, trial, model_name: str, X: pd.DataFrame, y: pd.Series) -> float:
        """Optuna objective function for hyperparameter tuning"""
        # Get base parameters
        params = get_model_params(model_name, self.config).copy()

        # Define hyperparameter search spaces
        if model_name == "random_forest":
            params['n_estimators'] = trial.suggest_int('n_estimators', 50, 300)
            params['max_depth'] = trial.suggest_int('max_depth', 3, 20)
            params['min_samples_split'] = trial.suggest_int('min_samples_split', 2, 20)
            params['min_samples_leaf'] = trial.suggest_int('min_samples_leaf', 1, 10)

        elif model_name == "xgboost":
            params['n_estimators'] = trial.suggest_int('n_estimators', 50, 300)
            params['max_depth'] = trial.suggest_int('max_depth', 3, 15)
            params['learning_rate'] = trial.suggest_float('learning_rate', 0.01, 0.3, log=True)
            params['subsample'] = trial.suggest_float('subsample', 0.6, 1.0)
            params['colsample_bytree'] = trial.suggest_float('colsample_bytree', 0.6, 1.0)

        elif model_name == "lightgbm":
            params['n_estimators'] = trial.suggest_int('n_estimators', 50, 300)
            params['max_depth'] = trial.suggest_int('max_depth', 3, 15)
            params['learning_rate'] = trial.suggest_float('learning_rate', 0.01, 0.3, log=True)
            params['subsample'] = trial.suggest_float('subsample', 0.6, 1.0)
            params['colsample_bytree'] = trial.suggest_float('colsample_bytree', 0.6, 1.0)

        # Create preprocessing pipeline
        preprocessing_pipeline = self.processor.create_preprocessing_pipeline(X)

        # Create model pipeline
        model = create_model_pipeline(
            preprocessing_pipeline,
            model_name,
            params,
            calibrate=False  # We'll calibrate after tuning
        )

        # Cross-validation
        cv = StratifiedKFold(
            n_splits=self.config['cv']['inner_splits'],
            shuffle=True,
            random_state=self.random_seed
        )

        # Use ROC-AUC as the optimization metric
        scores = cross_val_score(model, X, y, cv=cv, scoring='roc_auc')
        return scores.mean()

    def optimize_model(self, model_name: str, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Optimize hyperparameters for a model using Optuna"""
        print(f"Optimizing {model_name}...")

        study = optuna.create_study(
            direction='maximize',
            sampler=optuna.samplers.TPESampler(seed=self.random_seed)
        )
        study.optimize(
            lambda trial: self.objective(trial, model_name, X, y),
            n_trials=self.config['optuna']['n_trials'],
            timeout=self.config['optuna']['timeout']
        )

        print(f"Best ROC-AUC for {model_name}: {study.best_value:.4f}")
        print(f"Best parameters: {study.best_params}")

        # Update config with best parameters
        best_params = get_model_params(model_name, self.config).copy()
        best_params.update(study.best_params)
        return best_params

    def train_target(self, target: str, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Select on training folds, evaluate once on held-out patients, then refit."""
        print(f"\n=== Training models for {target} ===")
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, stratify=y, random_state=self.random_seed
        )
        model_names = self.config.get("model_candidates", ["logistic_regression", "random_forest", "xgboost"])
        results = {}
        for model_name in model_names:
            print(f"\nTraining {model_name}...")
            if model_name == "logistic_regression":
                best_params = get_model_params(model_name, self.config)
            else:
                best_params = self.optimize_model(model_name, X_train, y_train)
            candidate = create_model_pipeline(
                self.processor.create_preprocessing_pipeline(X_train),
                model_name, best_params, calibrate=False
            )
            cv = RepeatedStratifiedKFold(
                n_splits=self.config['cv']['outer_splits'],
                n_repeats=self.config['cv']['outer_repeats'],
                random_state=self.config['random_seeds']['cv_outer']
            )
            cv_scores = cross_val_score(candidate, X_train, y_train, cv=cv, scoring='roc_auc')
            results[model_name] = {
                'params': best_params,
                'cv_mean': float(cv_scores.mean()),
                'cv_std': float(cv_scores.std())
            }
            print(f"{model_name} training-fold ROC-AUC: {cv_scores.mean():.4f}")

        best_model_name = max(results, key=lambda name: results[name]['cv_mean'])
        best_result = results[best_model_name]
        evaluation_model = create_model_pipeline(
            self.processor.create_preprocessing_pipeline(X_train),
            best_model_name, best_result['params'], calibrate=True
        )
        evaluation_model.fit(X_train, y_train)
        y_pred = evaluation_model.predict(X_test)
        y_prob = evaluation_model.predict_proba(X_test)[:, 1]
        metrics = {
            'source': 'held_out',
            'evaluation_samples': int(len(X_test)),
            'cv_roc_auc_mean': best_result['cv_mean'],
            'cv_roc_auc_std': best_result['cv_std'],
            'accuracy': float(accuracy_score(y_test, y_pred)),
            'precision': float(precision_score(y_test, y_pred, zero_division=0)),
            'recall': float(recall_score(y_test, y_pred, zero_division=0)),
            'f1': float(f1_score(y_test, y_pred, zero_division=0)),
            'roc_auc': float(roc_auc_score(y_test, y_prob)),
            'pr_auc': float(average_precision_score(y_test, y_prob)),
            'brier_score': float(brier_score_loss(y_test, y_prob)),
        }
        final_model = create_model_pipeline(
            self.processor.create_preprocessing_pipeline(X),
            best_model_name, best_result['params'], calibrate=True
        )
        final_model.fit(X, y)
        print(f"\nBest model for {target}: {best_model_name}")
        print(f"Held-out ROC-AUC: {metrics['roc_auc']:.4f}")
        return {'model': final_model, 'model_name': best_model_name,
                'params': best_result['params'], 'metrics': metrics}

    def explain_model(self, model, X: pd.DataFrame, feature_names: list) -> Dict[str, Any]:
        """Generate SHAP explanations for the model"""
        # Extract the classifier from the pipeline
        if hasattr(model, 'named_steps'):
            # It's a pipeline
            preprocessor = model.named_steps['preprocessing']
            classifier = model.named_steps['classifier']
        else:
            # Direct model
            preprocessor = None
            classifier = model

        # Transform data if needed
        if preprocessor:
            X_transformed = preprocessor.transform(X)
            # Get feature names after preprocessing
            try:
                feature_names_out = preprocessor.get_feature_names_out(feature_names)
            except:
                feature_names_out = [f"feature_{i}" for i in range(X_transformed.shape[1])]
        else:
            X_transformed = X.values
            feature_names_out = feature_names

        # Create SHAP explainer
        if hasattr(classifier, 'calibrated_classifiers_') and len(classifier.calibrated_classifiers_) > 0:
            base_estimator = classifier.calibrated_classifiers_[0].estimator
        elif hasattr(classifier, 'estimator'):  # CalibratedClassifierCV
            base_estimator = classifier.estimator
        else:
            base_estimator = classifier

        # Use appropriate explainer based on model type
        # Tree-based models (RandomForest, XGBoost, LightGBM) have feature_importances_ or use TreeExplainer
        if str(type(base_estimator)).find('XGB') >= 0 or str(type(base_estimator)).find('LGBM') >= 0 or str(type(base_estimator)).find('RandomForest') >= 0:
            # Tree-based models
            explayer = shap.TreeExplainer(base_estimator)
        else:
            # Linear models (LogisticRegression, etc.)
            explayer = shap.LinearExplainer(base_estimator, X_transformed)

        # Calculate SHAP values
        shap_values = explayer.shap_values(X_transformed)

        # For binary classification, shap_values is a list of two arrays [class_0, class_1]
        # We want the SHAP values for class 1 (positive class)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
        elif shap_values.ndim == 3:
            shap_values = shap_values[:, :, 1]

        # Calculate mean absolute SHAP values for global importance
        mean_abs_shap = np.mean(np.abs(shap_values), axis=0)

        # Create feature importance dictionary
        feature_importance = dict(zip(feature_names_out, mean_abs_shap))
        feature_importance = dict(sorted(feature_importance.items(),
                                       key=lambda x: x[1], reverse=True))

        return {
            'shap_values': shap_values,
            'feature_names': feature_names_out,
            'feature_importance': feature_importance,
            'explainer': explayer
        }

    def save_artifacts(self, target: str, model_result: Dict[str, Any],
                      X: pd.DataFrame, y: pd.Series):
        """Save model, schema, metrics, and SHAP background"""
        # Save model
        model_path = self.artifacts_dir / "models" / f"{target}.joblib"
        joblib.dump(model_result['model'], model_path)
        print(f"Saved model to {model_path}")

        # Generate and save feature schema
        schema = self.processor.get_feature_schema(X)
        schema_path = self.artifacts_dir / "schema.json"
        with open(schema_path, 'w') as f:
            json.dump(schema, f, indent=2)
        print(f"Saved feature schema to {schema_path}")

        # Save metrics
        metrics = {
            'target': target,
            'model_type': model_result.get('model_name', type(model_result['model']).__name__),
            'parameters': model_result['params'],
            'metrics': model_result['metrics'],
            'feature_count': X.shape[1]
        }
        metrics_path = self.artifacts_dir / f"{target}_metrics.json"
        with open(metrics_path, 'w') as f:
            json.dump(metrics, f, indent=2)
        print(f"Saved metrics to {metrics_path}")

        # Generate SHAP explanations and save background (handle errors gracefully)
        try:
            explanation = self.explain_model(
                model_result['model'],
                X,
                list(X.columns)
            )

            # Save SHAP background (sample of training data)
            background_size = min(self.config['shap']['background_size'], len(X))
            background_sample = X.sample(n=background_size, random_state=self.random_seed)
            background_path = self.artifacts_dir / "shap_background.parquet"
            background_sample.to_parquet(background_path)
            print(f"Saved SHAP background to {background_path}")

            # Save global feature importances
            global_importance_path = self.artifacts_dir / f"{target}_shap_importance.json"
            with open(global_importance_path, 'w') as f:
                json.dump(explanation['feature_importance'], f, indent=2, default=float)
            print(f"Saved SHAP importance to {global_importance_path}")
        except Exception as e:
            print(f"Warning: Could not generate SHAP explanations: {e}")
            # Continue without SHAP explanations - model and metrics are still saved

    def train_all_targets(self):
        """Train models for all targets"""
        print("Loading and preparing data...")
        df = self.load_and_prepare_data()

        all_results = {}

        for target in self.targets:
            print(f"\n{'='*50}")
            print(f"TRAINING TARGET: {target}")
            print(f"{'='*50}")

            # Prepare features and target
            X, y = self.processor.prepare_features_targets(df, target)
            print(f"Features shape: {X.shape}")
            print(f"Target distribution: {y.value_counts().to_dict()}")

            # Train models for this target
            result = self.train_target(target, X, y)

            # Save artifacts
            self.save_artifacts(target, result, X, y)

            all_results[target] = result

        # Create manifest
        manifest = {
            'version': '1.0.0',
            'targets': self.targets,
            'training_date': pd.Timestamp.now().isoformat(),
            'random_seed': self.random_seed,
            'data_shape': df.shape,
            'feature_count': X.shape[1],
            'data_sha256': hashlib.sha256((Path(__file__).resolve().parents[3] / self.config['data_file']).read_bytes()).hexdigest(),
        }

        manifest_path = self.artifacts_dir / "manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        print(f"\nSaved manifest to {manifest_path}")

        return all_results


def main():
    """Main training function"""
    trainer = CardioLensTrainer()
    results = trainer.train_all_targets()

    print("\n" + "="*50)
    print("TRAINING COMPLETE")
    print("="*50)

    for target, result in results.items():
        print(f"{target}: {result['metrics']['roc_auc']:.4f} ROC-AUC "
              f"({type(result['model']).__name__})")


if __name__ == "__main__":
    main()
