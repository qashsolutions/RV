"""
Model evaluation, comparison, and visualization.
"""

import json
import os
import numpy as np
import pandas as pd
import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from features import engineer_features, get_feature_columns, get_target_column, load_data


def load_models(model_dir: str) -> dict:
    """Load all trained models from directory."""
    models = {}
    for f in os.listdir(model_dir):
        if f.endswith('.joblib'):
            name = f.replace('_model.joblib', '')
            models[name] = joblib.load(os.path.join(model_dir, f))
    return models


def evaluate_on_data(models: dict, data_path: str, output_dir: str = './evaluation'):
    """Full evaluation suite on a dataset."""
    os.makedirs(output_dir, exist_ok=True)

    # Load and engineer features
    df = load_data(data_path)
    df_feat, _ = engineer_features(df, is_training=True)

    feature_cols = get_feature_columns()
    target_col = get_target_column()
    available = [c for c in feature_cols if c in df_feat.columns]

    X = df_feat[available].fillna(0).values
    y = df_feat[target_col].values

    valid = np.isfinite(X).all(axis=1) & np.isfinite(y)
    X, y = X[valid], y[valid]

    # Load ensemble config
    config_path = os.path.join(os.path.dirname(data_path) if os.path.isfile(data_path)
                               else '.', 'trained_models', 'ensemble_config.json')
    weights = {}
    if os.path.exists(config_path):
        with open(config_path) as f:
            weights = json.load(f).get('weights', {})

    results = {}
    predictions = {}

    for name, model in models.items():
        pred = model.predict(X)
        predictions[name] = pred
        r2 = r2_score(y, pred)
        mae = mean_absolute_error(y, pred)
        rmse = np.sqrt(mean_squared_error(y, pred))
        results[name] = {'R²': r2, 'MAE': mae, 'RMSE': rmse}

    # Ensemble prediction
    if weights:
        ens_pred = np.zeros(len(X))
        for name in models:
            if name in weights:
                ens_pred += weights[name] * predictions[name]
        predictions['ensemble'] = ens_pred
        results['ensemble'] = {
            'R²': r2_score(y, ens_pred),
            'MAE': mean_absolute_error(y, ens_pred),
            'RMSE': np.sqrt(mean_squared_error(y, ens_pred)),
        }

    # Print results table
    print("\n" + "=" * 60)
    print(f"{'Model':<15} {'R²':>8} {'MAE':>8} {'RMSE':>8}")
    print("-" * 60)
    for name, metrics in results.items():
        print(f"{name:<15} {metrics['R²']:>8.4f} {metrics['MAE']:>8.4f} {metrics['RMSE']:>8.4f}")
    print("=" * 60)

    # Save results
    with open(os.path.join(output_dir, 'evaluation_results.json'), 'w') as f:
        json.dump(results, f, indent=2)

    # Plot: Actual vs Predicted
    fig, axes = plt.subplots(1, len(predictions), figsize=(6 * len(predictions), 5))
    if len(predictions) == 1:
        axes = [axes]
    for ax, (name, pred) in zip(axes, predictions.items()):
        ax.scatter(y, pred, alpha=0.5, s=10)
        ax.plot([0, 1.2], [0, 1.2], 'r--', lw=1)
        ax.set_xlabel('Actual Retention Ratio')
        ax.set_ylabel('Predicted Retention Ratio')
        ax.set_title(f'{name} (R²={results[name]["R²"]:.4f})')
        ax.set_xlim(0, 1.2)
        ax.set_ylim(0, 1.2)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'actual_vs_predicted.png'), dpi=150)
    plt.close()

    # Plot: Residuals
    fig, ax = plt.subplots(figsize=(10, 5))
    for name, pred in predictions.items():
        residuals = y - pred
        ax.hist(residuals, bins=50, alpha=0.5, label=name)
    ax.set_xlabel('Residual (Actual - Predicted)')
    ax.set_ylabel('Count')
    ax.set_title('Prediction Residuals')
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'residuals.png'), dpi=150)
    plt.close()

    print(f"\nPlots saved to {output_dir}/")
    return results


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', required=True, help='Path to evaluation data')
    parser.add_argument('--model-dir', default='./trained_models', help='Model directory')
    parser.add_argument('--output', default='./evaluation', help='Output directory')
    args = parser.parse_args()

    models = load_models(args.model_dir)
    evaluate_on_data(models, args.data, args.output)
