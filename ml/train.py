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
from fred_data import (
    fetch_all_series, merge_fred_features, get_fred_defaults, get_fred_feature_columns
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
        for f in sorted(path.glob('*.xlsx')) + sorted(path.glob('*.csv')) + sorted(path.glob('*.json')):
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
    parser.add_argument('--fred-api-key', default=os.environ.get('FRED_API_KEY', ''),
                        help='FRED API key (or set FRED_API_KEY env var)')
    args = parser.parse_args()

    df = load_all_data(args.data)
    print(f"Raw data: {df.shape[0]} rows, {df.shape[1]} columns")

    # Feature engineering
    df_feat, metadata = engineer_features(df, is_training=True)

    # Merge FRED macro-economic indicators
    fred_df = None
    if args.fred_api_key:
        print("\n--- FRED Economic Data Integration ---")
        try:
            fred_df = fetch_all_series(args.fred_api_key)
            df_feat = merge_fred_features(df_feat, fred_df)
        except Exception as e:
            print(f"Warning: FRED fetch failed ({e}), using defaults")
            from fred_data import _apply_defaults
            df_feat = _apply_defaults(df_feat)
    else:
        print("\nNo FRED API key provided (--fred-api-key or FRED_API_KEY env var)")
        print("Using default macro-economic values for all rows")
        from fred_data import _apply_defaults
        df_feat = _apply_defaults(df_feat)

    # Save FRED defaults to metadata for frontend inference
    metadata['fred_defaults'] = get_fred_defaults()
    metadata['fred_feature_columns'] = get_fred_feature_columns()

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

    # ======== IMPUTE MISSING SALE PRICES & GENERATE PRECOMPUTED ========
    if args.export_frontend and 'market_models' in dir() and 'rv_models' in dir():
        generate_precomputed(
            df_feat, available, market_models, market_weights,
            rv_models, rv_weights, args.export_frontend
        )

    print("\n\nAll training complete!")


def impute_missing_sales(df, feature_cols, market_models, market_weights):
    """
    For rows without Sales Price, predict it using the ensemble market model.
    Uses model disagreement to compute confidence intervals.
    Returns the dataframe with imputed values and confidence bands.
    """
    missing_mask = df['market_ratio'].isna() | ~np.isfinite(df['market_ratio'])
    has_mask = ~missing_mask

    if missing_mask.sum() == 0:
        print("No missing sales prices to impute.")
        return df

    print(f"\n{'='*50}")
    print(f"IMPUTING SALES PRICES FOR {missing_mask.sum()} ROWS")
    print(f"(using {has_mask.sum()} rows with known sales as training data)")
    print(f"{'='*50}")

    X_missing = df.loc[missing_mask, feature_cols].fillna(0).values
    valid = np.isfinite(X_missing).all(axis=1)
    valid_idx = df.loc[missing_mask].index[valid]
    X_missing = X_missing[valid]

    # Predict with each model in the ensemble
    predictions = {}
    for name, info in market_models.items():
        pred = info['model'].predict(X_missing)
        pred = np.clip(pred, 0.03, 0.95)
        predictions[name] = pred

    # Weighted ensemble prediction
    ensemble_pred = np.zeros(len(X_missing))
    for name, pred in predictions.items():
        ensemble_pred += market_weights[name] * pred

    # Confidence interval from model disagreement
    pred_matrix = np.column_stack(list(predictions.values()))
    pred_std = np.std(pred_matrix, axis=1)

    # Also compute global residual stats from training set for calibration
    has_data = df.loc[has_mask]
    X_has = has_data[feature_cols].fillna(0).values
    y_has = has_data['market_ratio'].values
    valid_has = np.isfinite(X_has).all(axis=1) & np.isfinite(y_has)
    X_has, y_has = X_has[valid_has], y_has[valid_has]

    ensemble_has = np.zeros(len(X_has))
    for name, info in market_models.items():
        ensemble_has += market_weights[name] * info['model'].predict(X_has)
    residuals = y_has - ensemble_has
    global_std = float(np.std(residuals))
    global_mae = float(np.mean(np.abs(residuals)))

    # Combined uncertainty: model disagreement + residual calibration
    # Use the larger of model std or calibrated residual std
    uncertainty = np.maximum(pred_std, global_std)

    # Set imputed values
    df.loc[valid_idx, 'market_ratio'] = ensemble_pred
    df.loc[valid_idx, 'market_ratio_low'] = np.clip(ensemble_pred - 1.645 * uncertainty, 0.03, 0.95)
    df.loc[valid_idx, 'market_ratio_high'] = np.clip(ensemble_pred + 1.645 * uncertainty, 0.03, 0.95)
    df.loc[valid_idx, 'is_imputed'] = True

    # Compute sale prices from ratios
    prices = df.loc[valid_idx, 'price']
    df.loc[valid_idx, 'sales_price'] = ensemble_pred * prices
    df.loc[valid_idx, 'sales_price_low'] = df.loc[valid_idx, 'market_ratio_low'] * prices
    df.loc[valid_idx, 'sales_price_high'] = df.loc[valid_idx, 'market_ratio_high'] * prices

    # Mark rows that already had data
    df.loc[has_mask, 'is_imputed'] = False
    df.loc[has_mask, 'market_ratio_low'] = df.loc[has_mask, 'market_ratio'] - 1.645 * global_std
    df.loc[has_mask, 'market_ratio_high'] = df.loc[has_mask, 'market_ratio'] + 1.645 * global_std
    df.loc[has_mask, 'market_ratio_low'] = df.loc[has_mask, 'market_ratio_low'].clip(0.03, 0.95)
    df.loc[has_mask, 'market_ratio_high'] = df.loc[has_mask, 'market_ratio_high'].clip(0.03, 0.95)

    print(f"Imputed {len(valid_idx)} rows")
    print(f"Mean imputed market ratio: {ensemble_pred.mean():.4f}")
    print(f"Mean uncertainty (std): {uncertainty.mean():.4f}")
    print(f"Global residual MAE: {global_mae:.4f}")
    print(f"90% CI width: +/- {(1.645 * uncertainty.mean()):.4f}")

    return df


def generate_precomputed(df, feature_cols, market_models, market_weights,
                         rv_models, rv_weights, output_dir):
    """Generate precomputed.json with imputed sales and prediction ranges."""

    # Impute missing sales prices first
    df = impute_missing_sales(df, feature_cols, market_models, market_weights)

    # ---- Compute stats ----
    stats = {}
    stats['total_records'] = int(len(df))
    stats['records_with_sales'] = int((~df.get('is_imputed', pd.Series(dtype=bool)).fillna(True)).sum())
    stats['records_imputed'] = int(df.get('is_imputed', pd.Series(dtype=bool)).fillna(False).sum())

    if 'brand_clean' in df.columns:
        stats['brands'] = sorted(df['brand_clean'].dropna().unique().tolist())
    if 'model' in df.columns:
        top_models = df['model'].value_counts().head(5).index.tolist()
        stats['models'] = top_models
    if 'model_line' in df.columns:
        stats['model_lines'] = sorted(df['model_line'].dropna().unique().tolist())

    if 'processor' in df.columns:
        stats['processors'] = sorted(df['processor'].dropna().unique().tolist())
    if 'ram_gb' in df.columns:
        stats['ram_values'] = sorted(df['ram_gb'].dropna().unique().tolist())
    if 'storage_gb' in df.columns:
        stats['storage_values'] = sorted(df['storage_gb'].dropna().unique().tolist())
    if 'screen_inches' in df.columns:
        stats['screen_sizes'] = sorted(df['screen_inches'].dropna().unique().tolist())
    if 'lease_duration_months' in df.columns:
        stats['terms'] = sorted(df['lease_duration_months'].dropna().unique().tolist())

    if 'price' in df.columns:
        p = df['price'].dropna()
        stats['price_range'] = {
            'min': float(p.min()), 'max': float(p.max()),
            'mean': float(p.mean()), 'median': float(p.median()),
        }

    if 'rv_ratio' in df.columns:
        r = df['rv_ratio'].dropna()
        stats['rv_ratio_stats'] = {
            'mean': float(r.mean()), 'std': float(r.std()),
            'min': float(r.min()), 'max': float(r.max()),
        }

    if 'market_ratio' in df.columns:
        m = df['market_ratio'].dropna()
        stats['market_ratio_stats'] = {
            'mean': float(m.mean()), 'std': float(m.std()),
            'min': float(m.min()), 'max': float(m.max()),
        }

    # RV accuracy (only on non-imputed rows)
    non_imputed = df[df.get('is_imputed', pd.Series(dtype=bool)).fillna(True) == False]
    if 'rv' in non_imputed.columns and 'sales_price' in non_imputed.columns:
        rv = pd.to_numeric(non_imputed['rv'], errors='coerce')
        sp = pd.to_numeric(non_imputed['sales_price'], errors='coerce')
        valid_both = rv.notna() & sp.notna()
        if valid_both.sum() > 0:
            diff = sp[valid_both] - rv[valid_both]
            stats['rv_accuracy'] = {
                'mean_diff': float(diff.mean()),
                'median_diff': float(diff.median()),
                'pct_below_rv': float((diff < 0).mean()),
                'pct_above_rv': float((diff > 0).mean()),
                'avg_loss_when_below': float(diff[diff < 0].mean()) if (diff < 0).sum() > 0 else 0,
                'avg_gain_when_above': float(diff[diff > 0].mean()) if (diff > 0).sum() > 0 else 0,
            }

    # Imputation quality stats
    if 'market_ratio_low' in df.columns:
        imputed = df[df.get('is_imputed', pd.Series(dtype=bool)).fillna(False) == True]
        if len(imputed) > 0:
            widths = imputed['market_ratio_high'] - imputed['market_ratio_low']
            stats['imputation_stats'] = {
                'count': int(len(imputed)),
                'mean_range_width': float(widths.mean()),
                'mean_predicted_ratio': float(imputed['market_ratio'].mean()),
                'mean_predicted_price': float(imputed['sales_price'].mean()) if 'sales_price' in imputed else 0,
            }

    # ---- Generate precomputed predictions with ranges ----
    configs = [
        # (label, model_line, model_tier, proc_tier, proc_gen, is_xeon, ram, storage, screen)
        ('Latitude 5000-i5-Gen10', 'business_standard', 5, 3, 10, False, 16, 256, 14.0),
        ('Latitude 5000-i5-Gen10', 'business_standard', 5, 3, 10, False, 16, 512, 14.0),
        ('Latitude 5000-i5-Gen11', 'business_standard', 5, 3, 11, False, 16, 256, 14.0),
        ('Latitude 5000-i5-Gen11', 'business_standard', 5, 3, 11, False, 16, 512, 14.0),
        ('Latitude 5000-i7-Gen10', 'business_standard', 5, 4, 10, False, 16, 512, 14.0),
        ('Latitude 5000-i7-Gen11', 'business_standard', 5, 4, 11, False, 16, 512, 14.0),
        ('Latitude 7000-i5-Gen10', 'business_standard', 7, 3, 10, False, 16, 256, 14.0),
        ('Latitude 7000-i5-Gen11', 'business_standard', 7, 3, 11, False, 16, 256, 14.0),
        ('Latitude 7000-i7-Gen10', 'business_standard', 7, 4, 10, False, 16, 512, 13.3),
        ('Latitude 7000-i7-Gen11', 'business_standard', 7, 4, 11, False, 16, 512, 13.3),
        ('Latitude 7000-i7-Gen11', 'business_standard', 7, 4, 11, False, 16, 512, 14.0),
        ('Latitude 7000-i7-Gen12', 'business_standard', 7, 4, 12, False, 16, 512, 14.0),
        ('Latitude 7000-i5-Gen11-8GB', 'business_standard', 7, 3, 11, False, 8, 256, 14.0),
        ('Latitude 7000-i7-Gen11-32GB', 'business_standard', 7, 4, 11, False, 32, 512, 14.0),
        ('Precision 7000-iX-Gen10', 'workstation', 7, 5, 10, True, 32, 1000, 15.6),
        ('Precision 7000-iX-Gen11', 'workstation', 7, 5, 11, True, 32, 1000, 15.6),
        ('Precision 7000-iX-Gen10-64GB', 'workstation', 7, 5, 10, True, 64, 1000, 15.6),
        ('Precision 5000-i7-Gen11', 'workstation', 5, 4, 11, False, 16, 512, 15.6),
        ('XPS 13-i7-Gen11', 'premium', 9, 4, 11, False, 16, 512, 13.3),
        ('XPS 15-i7-Gen11', 'premium', 9, 4, 11, False, 16, 512, 15.6),
    ]

    prices = [1200, 1500, 1800, 2000, 2500, 3000]
    terms = [24, 36]

    from features import (
        BRAND_TIER_ENCODING, BRAND_RETENTION, MODEL_LINE_ENCODING
    )

    # Get FRED defaults for precomputed predictions
    fred_defs = get_fred_defaults()

    predictions = []
    for cfg in configs:
        label, ml, mt, pt, pg, ix, ram, stor, scr = cfg
        ram_str = f'-{ram}GB' if ram != 16 else ''
        stor_str = f'-{stor}GB' if stor else ''
        config_name = f"{label}{ram_str}{stor_str}"

        for price in prices:
            for term in terms:
                age = term / 12.0
                bt = BRAND_TIER_ENCODING.get('Business', 3)
                br = BRAND_RETENTION.get('Dell', 0.98)
                mle = MODEL_LINE_ENCODING.get(ml, 3)
                rl = np.log2(max(1, ram))
                sl = np.log2(max(1, stor))
                sb = 1 if scr < 12.5 else 2 if scr <= 13.5 else 3 if scr <= 14.5 else 4 if scr <= 16 else 5
                pl = np.log1p(price)
                ptier = 1 if price < 1000 else 2 if price < 1500 else 3 if price < 2000 else 4 if price < 3000 else 5
                ss = (ram / 64.0 + stor / 2000.0 + pg / 13.0 + pt / 5.0) / 4

                features = np.array([[
                    age, age**2, term, bt, br, mle, mt, pg, pt,
                    1 if ix else 0, ram, rl, stor, sl, 1 if stor > 0 else 0,
                    scr, sb, pl, ptier, ss,
                    fred_defs['cpi_index'], fred_defs['cpi_yoy_change'],
                    fred_defs['consumer_sentiment'], fred_defs['fed_funds_rate'],
                    fred_defs['macro_score'],
                ]])

                # Market predictions with range
                market_preds = {}
                for name, info in market_models.items():
                    market_preds[name] = float(info['model'].predict(features)[0])
                market_ensemble = sum(market_weights[n] * p for n, p in market_preds.items())
                market_std = float(np.std(list(market_preds.values())))

                # RV predictions
                rv_preds = {}
                for name, info in rv_models.items():
                    rv_preds[name] = float(info['model'].predict(features)[0])
                rv_ensemble = sum(rv_weights[n] * p for n, p in rv_preds.items())

                mr = round(max(0.03, min(0.95, market_ensemble)), 4)
                mr_low = round(max(0.03, min(0.95, market_ensemble - 1.645 * max(market_std, 0.02))), 4)
                mr_high = round(max(0.03, min(0.95, market_ensemble + 1.645 * max(market_std, 0.02))), 4)
                rr = round(max(0.03, min(0.95, rv_ensemble)), 4)

                predictions.append({
                    'config': config_name,
                    'price': price,
                    'term': term,
                    'market_ratio': mr,
                    'market_ratio_low': mr_low,
                    'market_ratio_high': mr_high,
                    'rv_ratio': rr,
                    'market_value': round(mr * price, 2),
                    'market_value_low': round(mr_low * price, 2),
                    'market_value_high': round(mr_high * price, 2),
                    'rv_value': round(rr * price, 2),
                })

    output = {'stats': stats, 'predictions': predictions}
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, 'precomputed.json')
    with open(path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nPrecomputed data saved to {path}")
    print(f"  Stats keys: {list(stats.keys())}")
    print(f"  Predictions: {len(predictions)} configurations")


if __name__ == '__main__':
    main()
