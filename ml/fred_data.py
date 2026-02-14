"""
FRED (Federal Reserve Economic Data) integration for macro-economic features.

Fetches CPI, Consumer Sentiment, and Federal Funds Rate from the FRED API,
caches locally as CSV, and maps indicators to dates in the training data.

Requires: FRED_API_KEY environment variable or passed as argument.
Get a free key at: https://fred.stlouisfed.org/docs/api/api_key.html

FRED series used:
  - CPIAUCSL: Consumer Price Index for All Urban Consumers (monthly)
  - UMCSENT:  University of Michigan Consumer Sentiment (monthly)
  - FEDFUNDS: Effective Federal Funds Rate (monthly)
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

# Series IDs and their descriptions
FRED_SERIES = {
    'CPIAUCSL': 'Consumer Price Index (All Urban Consumers)',
    'UMCSENT': 'Consumer Sentiment (U. Michigan)',
    'FEDFUNDS': 'Federal Funds Rate',
}

CACHE_DIR = Path(__file__).parent / '.fred_cache'

# Defaults used when FRED data is unavailable (approximate 2024 values)
DEFAULTS = {
    'cpi_index': 314.0,       # CPI ~314 as of late 2024
    'cpi_yoy_change': 0.031,  # ~3.1% YoY inflation
    'consumer_sentiment': 67.0,  # UMCSENT ~67
    'fed_funds_rate': 5.33,   # ~5.33% fed funds rate
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
    cache_path = CACHE_DIR / 'fred_monthly.csv'

    if use_cache and cache_path.exists():
        cached = pd.read_csv(cache_path, parse_dates=['date'])
        age_days = (datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)).days
        if age_days < 30:
            print(f"Using cached FRED data ({len(cached)} rows, {age_days}d old)")
            return cached
        print(f"FRED cache is {age_days}d old, refreshing...")

    print("Fetching FRED economic indicators...")
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
    if 'CPIAUCSL' in merged.columns:
        # Year-over-year CPI change (inflation rate)
        merged['cpi_yoy_change'] = merged['CPIAUCSL'].pct_change(periods=12)

    # Cache
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    merged.to_csv(cache_path, index=False)
    print(f"Cached FRED data: {len(merged)} rows -> {cache_path}")

    return merged


def merge_fred_features(df: pd.DataFrame, fred_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge FRED economic indicators into the training DataFrame by date.

    Maps each row's end_date (lease end / sale date) to the nearest
    monthly FRED observation. Adds columns:
      - cpi_index: CPI level (normalized to 100-scale for model stability)
      - cpi_yoy_change: Year-over-year inflation rate
      - consumer_sentiment: U. Michigan sentiment index
      - fed_funds_rate: Effective federal funds rate
      - macro_score: Composite macro-economic health score
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
    if 'CPIAUCSL' in fred_df.columns:
        fred_cols.append('CPIAUCSL')
    if 'cpi_yoy_change' in fred_df.columns:
        fred_cols.append('cpi_yoy_change')
    if 'UMCSENT' in fred_df.columns:
        fred_cols.append('UMCSENT')
    if 'FEDFUNDS' in fred_df.columns:
        fred_cols.append('FEDFUNDS')

    fred_subset = fred_df[fred_cols].drop_duplicates(subset=['_fred_month'], keep='last')
    df = df.merge(fred_subset, on='_fred_month', how='left')
    df.drop(columns=['_fred_month'], inplace=True)

    # Rename to feature names
    rename_map = {}
    if 'CPIAUCSL' in df.columns:
        rename_map['CPIAUCSL'] = 'cpi_index'
    if 'UMCSENT' in df.columns:
        rename_map['UMCSENT'] = 'consumer_sentiment'
    if 'FEDFUNDS' in df.columns:
        rename_map['FEDFUNDS'] = 'fed_funds_rate'
    df.rename(columns=rename_map, inplace=True)

    # Fill any remaining NaN with defaults
    df['cpi_index'] = df.get('cpi_index', pd.Series(dtype=float)).fillna(DEFAULTS['cpi_index'])
    df['cpi_yoy_change'] = df.get('cpi_yoy_change', pd.Series(dtype=float)).fillna(DEFAULTS['cpi_yoy_change'])
    df['consumer_sentiment'] = df.get('consumer_sentiment', pd.Series(dtype=float)).fillna(DEFAULTS['consumer_sentiment'])
    df['fed_funds_rate'] = df.get('fed_funds_rate', pd.Series(dtype=float)).fillna(DEFAULTS['fed_funds_rate'])

    # Normalize CPI to 100-scale for model stability (base: 2020 CPI ~258)
    df['cpi_index'] = df['cpi_index'] / 258.0 * 100.0

    # Composite macro score (higher = healthier economy = stronger used laptop demand)
    # Weighted: sentiment (positive), low inflation (negative impact), moderate rates
    df['macro_score'] = (
        (df['consumer_sentiment'] / 100.0) * 0.4 +
        (1.0 - df['cpi_yoy_change'].clip(0, 0.10) / 0.10) * 0.3 +
        (1.0 - df['fed_funds_rate'].clip(0, 10) / 10.0) * 0.3
    )

    matched = df['cpi_index'].notna().sum()
    print(f"FRED features merged: {matched}/{len(df)} rows matched by date")

    return df


def _apply_defaults(df: pd.DataFrame) -> pd.DataFrame:
    """Apply default FRED values when API data is unavailable."""
    df['cpi_index'] = DEFAULTS['cpi_index'] / 258.0 * 100.0
    df['cpi_yoy_change'] = DEFAULTS['cpi_yoy_change']
    df['consumer_sentiment'] = DEFAULTS['consumer_sentiment']
    df['fed_funds_rate'] = DEFAULTS['fed_funds_rate']
    df['macro_score'] = (
        (DEFAULTS['consumer_sentiment'] / 100.0) * 0.4 +
        (1.0 - min(DEFAULTS['cpi_yoy_change'], 0.10) / 0.10) * 0.3 +
        (1.0 - min(DEFAULTS['fed_funds_rate'], 10) / 10.0) * 0.3
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
    cpi_norm = DEFAULTS['cpi_index'] / 258.0 * 100.0
    sentiment = DEFAULTS['consumer_sentiment']
    rate = DEFAULTS['fed_funds_rate']
    yoy = DEFAULTS['cpi_yoy_change']
    macro = (
        (sentiment / 100.0) * 0.4 +
        (1.0 - min(yoy, 0.10) / 0.10) * 0.3 +
        (1.0 - min(rate, 10) / 10.0) * 0.3
    )
    return {
        'cpi_index': round(cpi_norm, 4),
        'cpi_yoy_change': round(yoy, 4),
        'consumer_sentiment': round(sentiment, 2),
        'fed_funds_rate': round(rate, 2),
        'macro_score': round(macro, 4),
    }
