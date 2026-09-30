"""
Data loading and preprocessing for CardioLens
"""
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from typing import Tuple, List, Dict, Any
import yaml
import json
import os
from pathlib import Path


class CardioLensDataProcessor:
    """Handle data loading, cleaning, and preprocessing for CardioLens"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = str(Path(__file__).resolve().parents[2] / "config.yaml")
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.targets = self.config['targets']
        self.excluded_cols = self.config['excluded_cols']
        self.random_seed = self.config['random_seeds']['global']

        # Initialize processors
        self.scaler = StandardScaler()
        self.feature_schema = None

    def load_data(self, filepath: str = None) -> pd.DataFrame:
        """Load the CSV data"""
        if filepath is None:
            filepath = str(Path(__file__).resolve().parents[3] / self.config.get('data_file', 'file.csv'))
        df = pd.read_csv(filepath)
        return df

    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and preprocess the data"""
        df_clean = df.copy()

        # Standardize Sex column: handle typos and map to binary
        if 'Sex' in df_clean.columns:
            # Convert to string and strip whitespace
            df_clean['Sex'] = df_clean['Sex'].astype(str).str.strip()
            # Map variations: Female, Fmale, Male
            sex_mapping = {
                'Male': 1,
                'Female': 0,
                'Fmale': 0  # typo for Female
            }
            df_clean['Sex'] = df_clean['Sex'].map(sex_mapping)
            # Fill any NaN after mapping with 0
            df_clean['Sex'] = df_clean['Sex'].fillna(0)

        # Convert Y/N columns to binary
        binary_cols = ['Obesity', 'CRF', 'CVA', 'Airway disease',
                       'Thyroid Disease', 'CHF', 'DLP', 'Weak Peripheral Pulse',
                       'Lung rales', 'Systolic Murmur', 'Diastolic Murmur',
                       'Dyspnea', 'Atypical', 'Nonanginal', 'Exertional CP',
                       'LowTH Ang', 'LVH', 'Poor R Progression']

        for col in binary_cols:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].map({'Y': 1, 'N': 0})
                # Fill any NaN after mapping with 0
                df_clean[col] = df_clean[col].fillna(0)

        # These categorical findings need their own mappings; they are not Y/N labs.
        if 'BBB' in df_clean.columns:
            df_clean['BBB'] = df_clean['BBB'].map({'N': 0, 'LBBB': 1, 'RBBB': 2})
        if 'VHD' in df_clean.columns:
            df_clean['VHD'] = df_clean['VHD'].str.lower().map(
                {'n': 0, 'mild': 1, 'moderate': 2, 'severe': 3}
            )

        # Ensure all columns are numeric, coercing errors to NaN then filling with 0
        # Exclude target columns to preserve their original values for target creation
        target_cols = ['CAD', 'LAD', 'LCX', 'RCA', 'Cath']
        cols_to_process = [col for col in df_clean.columns if col not in target_cols]

        for col in cols_to_process:
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
            df_clean[col] = df_clean[col].fillna(0)

        return df_clean

    def prepare_features_targets(self, df: pd.DataFrame, target: str) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare features and target for a specific prediction task"""
        source = 'Cath' if target == 'CAD' else target
        if source not in df.columns:
            raise ValueError(f"Missing target column: {source}")
        # Create target variable
        if target == 'CAD':
            # Overall CAD status from Cath column
            labels = df['Cath'].astype(str).str.strip().str.lower()
            if not labels.isin(['cad', 'normal']).all():
                raise ValueError("Cath contains unsupported labels")
            y = labels.eq('cad').astype(int)
        else:
            # Vessel-specific stenosis
            labels = df[target].astype(str).str.strip().str.lower()
            if not labels.isin(['stenotic', 'stenosis', 'normal', 'n']).all():
                raise ValueError(f"{target} contains unsupported labels")
            y = labels.isin(['stenotic', 'stenosis']).astype(int)

        # Features: exclude target columns and other excluded cols
        excluded = set(self.excluded_cols) | {'CAD', 'Cath', 'LAD', 'LCX', 'RCA'}
        feature_cols = [col for col in df.columns if col not in excluded]

        X = df[feature_cols].copy()

        return X, y

    def get_feature_schema(self, X: pd.DataFrame) -> Dict[str, Any]:
        """Generate feature schema for API and UI"""
        schema = {}
        for col in X.columns:
            col_data = X[col]
            schema[col] = {
                'type': str(col_data.dtype),
                'min': float(col_data.min()) if np.issubdtype(col_data.dtype, np.number) else None,
                'max': float(col_data.max()) if np.issubdtype(col_data.dtype, np.number) else None,
                'default': float(col_data.median()) if np.issubdtype(col_data.dtype, np.number) else
                          col_data.mode().iloc[0] if not col_data.empty else None,
                'unit': self._get_unit(col),
                'reference_range': self._get_reference_range(col)
            }
        return schema

    def _get_unit(self, feature: str) -> str:
        """Get unit for feature (placeholder)"""
        units = {
            'Age': 'years',
            'Weight': 'kg',
            'Length': 'cm',
            'BMI': 'kg/m²',
            'BP': 'mmHg',
            'PR': 'bpm',
            'FBS': 'mg/dL',
            'BUN': 'mg/dL',
            'CR': 'mg/dL',
            'TG': 'mg/dL',
            'LDL': 'mg/dL',
            'HDL': 'mg/dL',
            'HB': 'g/dL',
            'K': 'mmol/L',
            'Na': 'mmol/L',
            'WBC': '/µL',
            'PLT': '10³/µL',
            'EF-TTE': '%'
        }
        return units.get(feature, '')

    def _get_reference_range(self, feature: str) -> List[float]:
        """Get reference range for feature (placeholder)"""
        ranges = {
            'Age': [0, 120],
            'Weight': [30, 200],
            'Length': [140, 220],
            'BMI': [15, 40],
            'BP': [90, 120],
            'PR': [60, 100],
            'FBS': [70, 100],
            'BUN': [7, 20],
            'CR': [0.5, 1.2],
            'TG': [0, 150],
            'LDL': [0, 100],
            'HDL': [40, 60],
            'HB': [12, 18],
            'K': [3.5, 5.0],
            'Na': [135, 145],
            'WBC': [4000, 11000],
            'PLT': [150, 400],
            'EF-TTE': [50, 75]
        }
        return ranges.get(feature, [0, 100])

    def create_preprocessing_pipeline(self, X: pd.DataFrame) -> Pipeline:
        """Create sklearn preprocessing pipeline"""
        # Identify numeric and categorical columns
        numeric_features = X.select_dtypes(include=[np.number]).columns.tolist()
        categorical_features = X.select_dtypes(include=['object', 'category']).columns.tolist()

        # For now, treat all as numeric (data appears to be mostly numeric)
        numeric_features = X.columns.tolist()
        categorical_features = []

        preprocessor = ColumnTransformer(
            transformers=[
                ('num', StandardScaler(), numeric_features),
                ('cat', OneHotEncoder(drop='first', sparse_output=False), categorical_features)
            ],
            remainder='passthrough'
        )

        return Pipeline([
            ('preprocessor', preprocessor)
        ])


def main():
    """Test the data processor"""
    processor = CardioLensDataProcessor()

    # Load data
    df = processor.load_data()
    print(f"Loaded data shape: {df.shape}")

    # Clean data
    df_clean = processor.clean_data(df)
    print(f"Cleaned data shape: {df_clean.shape}")

    # Prepare features and targets for each target
    for target in processor.targets:
        X, y = processor.prepare_features_targets(df_clean, target)
        print(f"\nTarget: {target}")
        print(f"Features shape: {X.shape}")
        print(f"Target distribution: {y.value_counts().to_dict()}")

        # Get feature schema
        schema = processor.get_feature_schema(X)
        print(f"Feature schema keys: {list(schema.keys())[:5]}...")


if __name__ == "__main__":
    main()
