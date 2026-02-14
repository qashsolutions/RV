"""
Training script for laptop residual value prediction.

Trains two model sets:
  1. Market Value model: predicts actual Sales Price / Purchase Price ratio
     (trained on rows with Sales Price data - ~7200 rows)
  2. RV model: predicts contractual RV / Purchase Price ratio
     (trained on all 11,184 rows)

Usage:
    python train.py --data ../data/LaptopPortfolio.xlsx
"""

import argparse
import os
import sys
import json
import warnings
import numpy as np
import pandas as pd
from pathlib import Path

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.tree import DecisionTreeRegressor
import xgboost as xgb
import lightgbm as lgb
import joblib

from features import (
    engineer_features, get_feature_columns, get_target_column,
    get_fallback_target, save_metadata, load_data
)

warnings.filterwarnings('ignore')

XGBOOST_PARAMS = {
    'n_estimators': 500,
    'max_depth': 6,
    'learning_rate': 0.05,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'min_child_weight': 3,
    'reg_alpha': 0.1,
    'reg_lambda': 1.0,
    'random_state': 42,
}

LIGHTGBM_PARAMS = {
    'n_estimators': 500,
    'max_depth': 6,
    'learning_rate': 0.05,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'min_child_samples': 10,
    'reg_alpha': 0.1,
    'reg_lambda': 1.0,
    'random_state': 42,
    'verbose': -1,
}

MDT_PARAMS = {
    'max_depth': 12,
    'min_samples_split': 10,
    'min_samples_leaf': 5,
    'random_state': 42,
}


def load_all_data(data_path: str) -> pd.DataFrame:
    path = Path(data_path)
    if path.is_file():
        print(f"Loading {path}")
        return load_data(str(path))
    if path.is_dir():
        frames = []
        for f in sorted(path.glob('*.xlsx')) + sorted(path.glob('*.csv')):
            print(f"Loading {f.name}...")
            frames.append(load_data(str(f)))
        if not frames:
            print(f"No data files in {path}")
            sys.exit(1)
        return pd.concat(frames, ignore_index=True)
    print(f"Not found: {data_path}")
    sys.exit(1)


def train_model_set(X_train, y_train, X_val, y_val, label=""):
    """Train XGBoost + LightGBM + MDT ensemble."""
    models = {}
    prefix = f"[{label}] " if label else ""

    # XGBoost
    print(f"\n{prefix}Training XGBoost...")
    m = xgb.XGBRegressor(**XGBOOST_PARAMS)
    m.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    pred = m.predict(X_val)
    r2 = r2_score(y_val, pred)
    mae = mean_absolute_error(y_val, pred)
    print(f"{prefix}XGBoost  R2={r2:.4f}  MAE={mae:.4f}")
    models['xgboost'] = {'model': m, 'r2': r2, 'mae': mae}

    # LightGBM
    print(f"\n{prefix}Training LightGBM...")
    m = lgb.LGBMRegressor(**LIGHTGBM_PARAMS)
    m.fit(X_train, y_train, eval_set=[(X_val, y_val)])
    pred = m.predict(X_val)
    r2 = r2_score(y_val, pred)
    mae = mean_absolute_error(y_val, pred)
    print(f"{prefix}LightGBM R2={r2:.4f}  MAE={mae:.4f}")
    models['lightgbm'] = {'model': m, 'r2': r2, 'mae': mae}

    # MDT
    print(f"\n{prefix}Training MDT...")
    m = DecisionTreeRegressor(**MDT_PARAMS)
    m.fit(X_train, y_train)
    pred = m.predict(X_val)
    r2 = r2_score(y_val, pred)
    mae = mean_absolute_error(y_val, pred)
    print(f"{prefix}MDT      R2={r2:.4f}  MAE={mae:.4f}")
    models['mdt'] = {'model': m, 'r2': r2, 'mae': mae}

    return models


def ensemble_weights(models):
    scores = {n: max(0, m['r2']) for n, m in models.items()}
    total = sum(scores.values())
    if total == 0:
        return {n: 1/len(models) for n in models}
    return {n: s/total for n, s in scores.items()}


def evaluate_ensemble(models, weights, X_val, y_val, label=""):
    prefix = f"[{label}] " if label else ""
    preds = {}
    ens = np.zeros(len(X_val))
    for name, info in models.items():
        p = info['model'].predict(X_val)
        preds[name] = p
        ens += weights[name] * p

    r2 = r2_score(y_val, ens)
    mae = mean_absolute_error(y_val, ens)
    rmse = np.sqrt(mean_squared_error(y_val, ens))

    # Confidence from model agreement
    pred_matrix = np.column_stack(list(preds.values()))
    avg_std = np.mean(np.std(pred_matrix, axis=1))

    print(f"\n{'='*50}")
    print(f"{prefix}ENSEMBLE RESULTS")
    print(f"{'='*50}")
    print(f"R2:         {r2:.4f}")
    print(f"MAE:        {mae:.4f}")
    print(f"RMSE:       {rmse:.4f}")
    print(f"Avg StdDev: {avg_std:.4f}")
    print(f"Weights:    { {k: round(v,3) for k,v in weights.items()} }")

    return {'r2': float(r2), 'mae': float(mae), 'rmse': float(rmse), 'avg_std': float(avg_std)}


def save_all(models, weights, metadata, metrics, feature_cols, output_dir, prefix=""):
    os.makedirs(output_dir, exist_ok=True)
    p = f"{prefix}_" if prefix else ""

    for name, info in models.items():
        path = os.path.join(output_dir, f'{p}{name}_model.joblib')
        joblib.dump(info['model'], path)

    config = {
        'prefix': prefix,
        'weights': weights,
        'feature_columns': feature_cols,
        'model_scores': {n: {'r2': float(m['r2']), 'mae': float(m['mae'])} for n, m in models.items()},
        'ensemble_metrics': metrics,
    }
    with open(os.path.join(output_dir, f'{p}ensemble_config.json'), 'w') as f:
        json.dump(config, f, indent=2)

    save_metadata(metadata, output_dir)
    print(f"Saved {prefix or 'default'} models to {output_dir}")


def print_importance(models, features, label=""):
    prefix = f"[{label}] " if label else ""
    print(f"\n{prefix}Feature Importance (top 10):")
    for name, info in models.items():
        m = info['model']
        if hasattr(m, 'feature_importances_'):
            imp = m.feature_importances_
            idx = np.argsort(imp)[::-1]
            print(f"\n  {name}:")
            for i in idx[:10]:
                if i < len(features):
                    print(f"    {features[i]:30s} {imp[i]:.4f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', required=True)
    parser.add_argument('--output', default='./trained_models')
    parser.add_argument('--export-frontend', default='../frontend/public/models')
    parser.add_argument('--test-size', type=float, default=0.2)
    args = parser.parse_args()

    df = load_all_data(args.data)
    print(f"Raw data: {df.shape[0]} rows, {df.shape[1]} columns")

    # Feature engineering
    df_feat, metadata = engineer_features(df, is_training=True)

    feature_cols = get_feature_columns()
    available = [c for c in feature_cols if c in df_feat.columns]
    missing = [c for c in feature_cols if c not in df_feat.columns]
    if missing:
        print(f"Missing features (defaults used): {missing}")
    print(f"Using {len(available)} features: {available}")

    # ======== MODEL 1: Market Value (actual sales price) ========
    target_market = get_target_column()  # 'market_ratio'
    if target_market in df_feat.columns:
        mask = df_feat[target_market].notna() & np.isfinite(df_feat[target_market])
        df_market = df_feat[mask]
        X_m = df_market[available].fillna(0).values
        y_m = df_market[target_market].values

        valid = np.isfinite(X_m).all(axis=1) & np.isfinite(y_m)
        X_m, y_m = X_m[valid], y_m[valid]
        print(f"\n{'='*50}")
        print(f"MARKET VALUE MODEL ({len(X_m)} samples with sales price)")
        print(f"{'='*50}")

        if len(X_m) >= 50:
            Xtr, Xvl, ytr, yvl = train_test_split(X_m, y_m, test_size=args.test_size, random_state=42)
            print(f"Train: {len(Xtr)}, Val: {len(Xvl)}")

            market_models = train_model_set(Xtr, ytr, Xvl, yvl, label="Market")
            market_weights = ensemble_weights(market_models)
            market_metrics = evaluate_ensemble(market_models, market_weights, Xvl, yvl, label="Market")
            print_importance(market_models, available, label="Market")

            save_all(market_models, market_weights, metadata, market_metrics,
                     available, args.output, prefix="market")
            if args.export_frontend:
                save_all(market_models, market_weights, metadata, market_metrics,
                         available, args.export_frontend, prefix="market")

            # Also analyze RV accuracy vs actual sales
            if 'rv' in df_market.columns and 'sales_price' in df_market.columns:
                rv_vals = pd.to_numeric(df_market['rv'], errors='coerce')
                sp_vals = pd.to_numeric(df_market['sales_price'], errors='coerce')
                valid_both = rv_vals.notna() & sp_vals.notna()
                if valid_both.sum() > 0:
                    diff = sp_vals[valid_both] - rv_vals[valid_both]
                    print(f"\n--- RV vs Actual Sales Analysis ---")
                    print(f"Mean difference (Sales - RV): ${diff.mean():.2f}")
                    print(f"Median difference: ${diff.median():.2f}")
                    print(f"% sold below RV: {(diff < 0).mean():.1%}")
                    print(f"% sold above RV: {(diff > 0).mean():.1%}")
                    print(f"Avg loss when below RV: ${diff[diff < 0].mean():.2f}")
        else:
            print(f"Not enough market data ({len(X_m)} samples)")

    # ======== MODEL 2: RV Model (contractual residual value) ========
    target_rv = get_fallback_target()  # 'rv_ratio'
    if target_rv in df_feat.columns:
        mask = df_feat[target_rv].notna() & np.isfinite(df_feat[target_rv])
        df_rv = df_feat[mask]
        X_r = df_rv[available].fillna(0).values
        y_r = df_rv[target_rv].values

        valid = np.isfinite(X_r).all(axis=1) & np.isfinite(y_r)
        X_r, y_r = X_r[valid], y_r[valid]
        print(f"\n{'='*50}")
        print(f"RV MODEL ({len(X_r)} samples - all data)")
        print(f"{'='*50}")

        if len(X_r) >= 50:
            Xtr, Xvl, ytr, yvl = train_test_split(X_r, y_r, test_size=args.test_size, random_state=42)
            print(f"Train: {len(Xtr)}, Val: {len(Xvl)}")

            rv_models = train_model_set(Xtr, ytr, Xvl, yvl, label="RV")
            rv_weights = ensemble_weights(rv_models)
            rv_metrics = evaluate_ensemble(rv_models, rv_weights, Xvl, yvl, label="RV")
            print_importance(rv_models, available, label="RV")

            save_all(rv_models, rv_weights, metadata, rv_metrics,
                     available, args.output, prefix="rv")
            if args.export_frontend:
                save_all(rv_models, rv_weights, metadata, rv_metrics,
                         available, args.export_frontend, prefix="rv")

    print("\n\nAll training complete!")


if __name__ == '__main__':
    main()
