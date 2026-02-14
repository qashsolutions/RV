"""
FRED (Federal Reserve Economic Data) integration for ASEAN macro-economic features.

Fetches ASEAN-relevant indicators from FRED:
  - DEXSIUS:          USD/SGD exchange rate (primary ASEAN B2B market)
  - SGPCPIALLMINMEI:  Singapore CPI (ASEAN inflation proxy)
  - PCU33443344:      US PPI Semiconductors (global component cost proxy)

These replace the original US-centric series (CPI, UMCSENT, FEDFUNDS) because:
  - Dell laptops are priced in USD, sold in ASEAN local currency
  - USD/SGD is the #1 external driver: when USD strengthens, used laptops
    become cheaper in local terms → lower resale values
  - Singapore CPI reflects ASEAN buyer purchasing power, not US consumers
  - Semiconductor PPI is global (supply chain is worldwide), so US series is valid

Requires: FRED_API_KEY environment variable or passed as argument.
Get a free key at: https://fred.stlouisfed.org/docs/api/api_key.html
"""

import os
import json
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

# ASEAN-relevant FRED series
FRED_SERIES = {
    'DEXSIUS': 'USD/SGD Exchange Rate',
    'SGPCPIALLMINMEI': 'Singapore CPI (All Items)',
    'PCU33443344': 'PPI Semiconductors (global proxy)',
}

CACHE_DIR = Path(__file__).parent / '.fred_cache'

# Defaults used when FRED data is unavailable (approximate 2024 values)
DEFAULTS = {
    'cpi_index': 117.5,         # Singapore CPI ~117.5 (base 2019=100)
    'cpi_yoy_change': 0.028,    # ~2.8% YoY Singapore inflation (2024)
    'consumer_sentiment': 1.34,  # USD/SGD rate ~1.34 (proxy for ASEAN demand)
    'fed_funds_rate': 107.0,    # Semiconductor PPI index ~107 (2017=100)
}


def _fetch_fred_series(series_id: str, api_key: str,
                       start: str = '2015-01-01',
                       end: Optional[str] = None) -> pd.DataFrame:
    """Fetch a single FRED series via the FRED API (no fredapi dependency)."""
    if not end:
        end = datetime.now().strftime('%Y-%m-%d')

    params = urllib.parse.urlencode({
        'series_id': series_id,
        'api_key': api_key,
        'file_type': 'json',
        'observation_start': start,
        'observation_end': end,
        'frequency': 'm',  # monthly
    })
    url = f'https://api.stlouisfed.org/fred/series/observations?{params}'

    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())

    observations = data.get('observations', [])
    if not observations:
        print(f"  Warning: No observations returned for {series_id}")
        return pd.DataFrame(columns=['date', series_id])

    rows = []
    for obs in observations:
        val = obs.get('value', '.')
        if val == '.':
            continue
        rows.append({
            'date': pd.Timestamp(obs['date']),
            series_id: float(val),
        })

    df = pd.DataFrame(rows)
    return df


def fetch_all_series(api_key: str, use_cache: bool = True) -> pd.DataFrame:
    """
    Fetch all FRED series, merge into a single monthly DataFrame.
    Caches to disk to avoid repeated API calls.
    """
    cache_path = CACHE_DIR / 'fred_asean_monthly.csv'

    if use_cache and cache_path.exists():
        cached = pd.read_csv(cache_path, parse_dates=['date'])
        age_days = (datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)).days
        if age_days < 30:
            print(f"Using cached FRED ASEAN data ({len(cached)} rows, {age_days}d old)")
            return cached
        print(f"FRED cache is {age_days}d old, refreshing...")

    print("Fetching FRED ASEAN economic indicators...")
    merged = None

    for series_id, desc in FRED_SERIES.items():
        print(f"  Fetching {series_id} ({desc})...")
        try:
            df = _fetch_fred_series(series_id, api_key)
            if merged is None:
                merged = df
            else:
                merged = pd.merge(merged, df, on='date', how='outer')
        except Exception as e:
            print(f"  Warning: Failed to fetch {series_id}: {e}")

    if merged is None or len(merged) == 0:
        print("Warning: No FRED data fetched, using defaults")
        return pd.DataFrame()

    merged = merged.sort_values('date').reset_index(drop=True)

    # Forward-fill gaps (some series may have different reporting dates)
    merged = merged.ffill()

    # Compute derived features
    if 'SGPCPIALLMINMEI' in merged.columns:
        # Year-over-year CPI change (Singapore inflation rate)
        merged['cpi_yoy_change'] = merged['SGPCPIALLMINMEI'].pct_change(periods=12)

    # Cache
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    merged.to_csv(cache_path, index=False)
    print(f"Cached FRED ASEAN data: {len(merged)} rows -> {cache_path}")

    return merged


def merge_fred_features(df: pd.DataFrame, fred_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge FRED ASEAN economic indicators into the training DataFrame by date.

    Maps each row's end_date (lease end / sale date) to the nearest
    monthly FRED observation. Adds columns (names kept stable for model compatibility):
      - cpi_index: Singapore CPI (normalized to 100-scale)
      - cpi_yoy_change: Year-over-year Singapore inflation rate
      - consumer_sentiment: USD/SGD exchange rate (demand/currency proxy)
      - fed_funds_rate: Semiconductor PPI (global component cost proxy)
      - macro_score: Composite ASEAN macro score
    """
    df = df.copy()

    # Determine the date column to use for matching
    date_col = None
    for candidate in ['end_date', 'start_date']:
        if candidate in df.columns and pd.api.types.is_datetime64_any_dtype(df[candidate]):
            date_col = candidate
            break

    if date_col is None:
        print("Warning: No date column found, using FRED defaults")
        return _apply_defaults(df)

    if fred_df is None or len(fred_df) == 0:
        print("Warning: No FRED data available, using defaults")
        return _apply_defaults(df)

    # Round training dates to month start for matching
    df['_fred_month'] = df[date_col].dt.to_period('M').dt.to_timestamp()
    fred_df = fred_df.copy()
    fred_df['_fred_month'] = fred_df['date'].dt.to_period('M').dt.to_timestamp()

    # Merge on month
    fred_cols = ['_fred_month']
    for col in ['SGPCPIALLMINMEI', 'cpi_yoy_change', 'DEXSIUS', 'PCU33443344']:
        if col in fred_df.columns:
            fred_cols.append(col)

    fred_subset = fred_df[fred_cols].drop_duplicates(subset=['_fred_month'], keep='last')
    df = df.merge(fred_subset, on='_fred_month', how='left')
    df.drop(columns=['_fred_month'], inplace=True)

    # Rename to feature names (kept stable for model compatibility)
    rename_map = {}
    if 'SGPCPIALLMINMEI' in df.columns:
        rename_map['SGPCPIALLMINMEI'] = 'cpi_index'
    if 'DEXSIUS' in df.columns:
        rename_map['DEXSIUS'] = 'consumer_sentiment'  # USD/SGD rate
    if 'PCU33443344' in df.columns:
        rename_map['PCU33443344'] = 'fed_funds_rate'   # Semiconductor PPI
    df.rename(columns=rename_map, inplace=True)

    # Fill any remaining NaN with defaults
    df['cpi_index'] = df.get('cpi_index', pd.Series(dtype=float)).fillna(DEFAULTS['cpi_index'])
    df['cpi_yoy_change'] = df.get('cpi_yoy_change', pd.Series(dtype=float)).fillna(DEFAULTS['cpi_yoy_change'])
    df['consumer_sentiment'] = df.get('consumer_sentiment', pd.Series(dtype=float)).fillna(DEFAULTS['consumer_sentiment'])
    df['fed_funds_rate'] = df.get('fed_funds_rate', pd.Series(dtype=float)).fillna(DEFAULTS['fed_funds_rate'])

    # Normalize Singapore CPI to 100-scale (base: 2019 SG CPI ~100)
    df['cpi_index'] = df['cpi_index'] / 100.0 * 100.0  # Already ~100-based, keep as-is

    # Composite ASEAN macro score (higher = stronger used laptop demand)
    # Weighted: weak USD/SGD (strong SGD = higher local purchasing power),
    #           low inflation, low component costs (cheaper replacement = lower RV)
    df['macro_score'] = (
        (1.0 / df['consumer_sentiment'].clip(1.0, 2.0)) * 0.4 +  # Strong SGD = high demand
        (1.0 - df['cpi_yoy_change'].clip(0, 0.10) / 0.10) * 0.3 +  # Low inflation = good
        (1.0 - (df['fed_funds_rate'].clip(80, 130) - 80) / 50.0) * 0.3  # Low semi cost = cheaper new laptops
    )

    matched = df['cpi_index'].notna().sum()
    print(f"FRED ASEAN features merged: {matched}/{len(df)} rows matched by date")

    return df


def _apply_defaults(df: pd.DataFrame) -> pd.DataFrame:
    """Apply default FRED ASEAN values when API data is unavailable."""
    df['cpi_index'] = DEFAULTS['cpi_index']
    df['cpi_yoy_change'] = DEFAULTS['cpi_yoy_change']
    df['consumer_sentiment'] = DEFAULTS['consumer_sentiment']
    df['fed_funds_rate'] = DEFAULTS['fed_funds_rate']
    df['macro_score'] = (
        (1.0 / min(max(DEFAULTS['consumer_sentiment'], 1.0), 2.0)) * 0.4 +
        (1.0 - min(DEFAULTS['cpi_yoy_change'], 0.10) / 0.10) * 0.3 +
        (1.0 - (min(max(DEFAULTS['fed_funds_rate'], 80), 130) - 80) / 50.0) * 0.3
    )
    return df


def get_fred_feature_columns():
    """Return the list of FRED-derived feature column names."""
    return [
        'cpi_index',
        'cpi_yoy_change',
        'consumer_sentiment',
        'fed_funds_rate',
        'macro_score',
    ]


def get_fred_defaults():
    """Return current default values for frontend/inference use."""
    cpi_norm = DEFAULTS['cpi_index']
    usd_sgd = DEFAULTS['consumer_sentiment']
    semi_ppi = DEFAULTS['fed_funds_rate']
    yoy = DEFAULTS['cpi_yoy_change']
    macro = (
        (1.0 / min(max(usd_sgd, 1.0), 2.0)) * 0.4 +
        (1.0 - min(yoy, 0.10) / 0.10) * 0.3 +
        (1.0 - (min(max(semi_ppi, 80), 130) - 80) / 50.0) * 0.3
    )
    return {
        'cpi_index': round(cpi_norm, 4),
        'cpi_yoy_change': round(yoy, 4),
        'consumer_sentiment': round(usd_sgd, 4),
        'fed_funds_rate': round(semi_ppi, 2),
        'macro_score': round(macro, 4),
    }
