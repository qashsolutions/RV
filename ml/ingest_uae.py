"""
UAE marketplace data ingestion pipeline.

Converts scraped UAE laptop resale data (JSON) into the same format
as LaptopPortfolio.xlsx so it can be fed directly into the training pipeline.

Key transformations:
  - Estimates original purchase price (MSRP) from specs + processor generation
  - Derives laptop age from processor generation (since model_year/age_months are null)
  - Maps JSON fields to the portfolio column format
  - Handles multi-brand (Dell, HP, Apple, Lenovo)
  - Uses USD prices only
"""

import json
import re
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ============================================================
# MSRP ESTIMATION TABLE
# Estimated original purchase prices by brand + segment + specs.
# Derived from historical launch prices and spec-tier analysis.
# ============================================================

# Processor generation → approximate release year
PROC_GEN_YEAR = {
    4: 2013, 5: 2015, 6: 2016, 7: 2017, 8: 2018,
    9: 2019, 10: 2020, 11: 2021, 12: 2022, 13: 2023, 14: 2024,
}

# For Apple M-series processors
APPLE_CHIP_YEAR = {
    'm1': 2020, 'm2': 2022, 'm3': 2023, 'm4': 2024,
}

# Base MSRP by brand × segment × processor tier (USD)
# Format: (brand, segment) → {proc_tier: base_msrp}
BASE_MSRP: Dict[tuple, Dict[int, float]] = {
    # Dell
    ('Dell', 'business_standard'): {2: 700, 3: 900, 4: 1200, 5: 1800},
    ('Dell', 'workstation'):       {3: 1500, 4: 2200, 5: 3200},
    ('Dell', 'premium'):           {3: 1000, 4: 1400, 5: 2000},
    ('Dell', 'sme'):               {2: 500, 3: 700, 4: 1000, 5: 1400},
    ('Dell', 'consumer'):          {2: 400, 3: 600, 4: 900, 5: 1300},
    # HP
    ('HP', 'business_standard'):   {2: 700, 3: 900, 4: 1200, 5: 1800},
    ('HP', 'workstation'):         {3: 1500, 4: 2200, 5: 3200},
    ('HP', 'premium'):             {3: 1000, 4: 1400, 5: 2000},
    ('HP', 'sme'):                 {2: 500, 3: 700, 4: 1000, 5: 1400},
    ('HP', 'consumer'):            {2: 400, 3: 600, 4: 900, 5: 1300},
    # Lenovo
    ('Lenovo', 'business_standard'): {2: 650, 3: 850, 4: 1150, 5: 1700},
    ('Lenovo', 'workstation'):       {3: 1400, 4: 2100, 5: 3000},
    ('Lenovo', 'premium'):           {3: 900, 4: 1300, 5: 1900},
    ('Lenovo', 'consumer'):          {2: 400, 3: 550, 4: 800, 5: 1200},
    # Apple
    ('Apple', 'premium'):          {3: 1300, 4: 1800, 5: 2500},
}

# RAM premium: additional cost for above-base RAM
RAM_PREMIUM = {
    4: -100, 8: 0, 16: 100, 32: 300, 64: 600, 128: 1200,
}

# Storage premium: additional cost for above-base storage
STORAGE_PREMIUM = {
    128: -50, 256: 0, 512: 80, 1000: 200, 2000: 400,
}

# Year-over-year price inflation for new laptops (~2-3%)
ANNUAL_PRICE_INFLATION = 0.025

# Model line keywords for each brand
MODEL_LINE_PATTERNS = {
    'Dell': {
        'latitude': 'business_standard',
        'precision': 'workstation',
        'xps': 'premium',
        'inspiron': 'consumer',
        'vostro': 'sme',
        'optiplex': 'desktop',
    },
    'HP': {
        'elitebook': 'business_standard',
        'probook': 'sme',
        'zbook': 'workstation',
        'spectre': 'premium',
        'envy': 'premium',
        'pavilion': 'consumer',
        'omen': 'consumer',
        'victus': 'consumer',
    },
    'Lenovo': {
        'thinkpad': 'business_standard',
        'thinkstation': 'workstation',
        'yoga': 'premium',
        'ideapad': 'consumer',
        'legion': 'consumer',
        'v': 'sme',
    },
    'Apple': {
        'macbook pro': 'premium',
        'macbook air': 'premium',
        'macbook': 'premium',
    },
}


def parse_processor_info(proc_str: str) -> Dict:
    """
    Parse processor string into structured info.
    Examples:
      "Core i5-5300U"    → gen=5, tier=3
      "Core i7-1365U"    → gen=13, tier=4
      "Xeon W-10855M"    → gen=10, tier=5
      "Apple M2"         → gen=14 (mapped), tier=4
      "Ryzen 5 5600U"    → gen=5, tier=3
    """
    if not proc_str or pd.isna(proc_str):
        return {'gen': 0, 'tier': 3, 'is_xeon': False, 'year': 2020}

    s = str(proc_str).strip()
    result = {'gen': 0, 'tier': 3, 'is_xeon': False, 'year': 2020}

    # Apple M-series
    m_match = re.search(r'\b(m[1-4])\b', s.lower())
    if m_match:
        chip = m_match.group(1)
        result['year'] = APPLE_CHIP_YEAR.get(chip, 2022)
        result['gen'] = 14  # map to latest for feature engineering
        # Pro/Max variants
        if 'max' in s.lower() or 'ultra' in s.lower():
            result['tier'] = 5
        elif 'pro' in s.lower():
            result['tier'] = 4
        else:
            result['tier'] = 3
        return result

    # Intel Xeon
    if 'xeon' in s.lower():
        result['is_xeon'] = True
        result['tier'] = 5
        gen_match = re.search(r'W-(\d{2})\d{2,3}', s)
        if gen_match:
            result['gen'] = int(gen_match.group(1))
        else:
            result['gen'] = 10  # default Xeon
        result['year'] = PROC_GEN_YEAR.get(result['gen'], 2020)
        return result

    # Intel Core i-series: "Core i7-1365U", "i5-5300U", "Core i7 - 11 Gen"
    # Tier
    if 'i9' in s.lower():
        result['tier'] = 5
    elif 'i7' in s.lower():
        result['tier'] = 4
    elif 'i5' in s.lower():
        result['tier'] = 3
    elif 'i3' in s.lower():
        result['tier'] = 2
    else:
        result['tier'] = 1

    # Generation from "N Gen" or "NNth Gen"
    gen_match = re.search(r'(\d+)\s*(?:th\s*)?Gen', s, re.IGNORECASE)
    if gen_match:
        result['gen'] = int(gen_match.group(1))
    else:
        # From model number: i7-1185G7 → gen 11, i5-10310U → gen 10, i5-5300U → gen 5
        mod_match = re.search(r'i[3579]-(\d{2})\d{2,3}', s)
        if mod_match:
            result['gen'] = int(mod_match.group(1))
        else:
            mod_match = re.search(r'i[3579]-(\d)\d{3}', s)
            if mod_match:
                result['gen'] = int(mod_match.group(1))

    result['year'] = PROC_GEN_YEAR.get(result['gen'], 2020)

    # AMD Ryzen
    if 'ryzen' in s.lower():
        ryzen_match = re.search(r'ryzen\s*(\d)', s.lower())
        if ryzen_match:
            r_tier = int(ryzen_match.group(1))
            result['tier'] = {3: 2, 5: 3, 7: 4, 9: 5}.get(r_tier, 3)
        # Ryzen gen from model: "5600U" → ~gen 11 equivalent
        rmod = re.search(r'(\d)\d{3}', s)
        if rmod:
            ryzen_series = int(rmod.group(1))
            result['gen'] = {3: 9, 4: 10, 5: 11, 6: 12, 7: 13}.get(ryzen_series, 11)
            result['year'] = PROC_GEN_YEAR.get(result['gen'], 2021)

    return result


def detect_model_line(brand: str, model_series: str) -> str:
    """Detect model line from brand + model string."""
    if not model_series or pd.isna(model_series):
        return 'unknown'

    s = model_series.lower().strip()
    patterns = MODEL_LINE_PATTERNS.get(brand, {})

    for keyword, line in patterns.items():
        if keyword in s:
            return line

    return 'unknown'


def extract_model_number(model_series: str) -> Optional[int]:
    """Extract 4-digit model number from model string."""
    if not model_series or pd.isna(model_series):
        return None
    match = re.search(r'(\d{4})', str(model_series))
    if match:
        return int(match.group(1))
    return None


def estimate_msrp(
    brand: str,
    model_line: str,
    proc_tier: int,
    proc_gen: int,
    ram_gb: int,
    storage_gb: int,
    proc_year: int,
) -> float:
    """
    Estimate the original purchase price (MSRP) of a laptop.

    Uses base MSRP tables adjusted for:
      - RAM/storage premiums vs baseline
      - Price inflation relative to release year
      - Unknown brand/segment fallbacks
    """
    key = (brand, model_line)
    tier_prices = BASE_MSRP.get(key)

    if not tier_prices:
        # Fallback: use Dell equivalent
        fallback_key = ('Dell', model_line if model_line != 'unknown' else 'business_standard')
        tier_prices = BASE_MSRP.get(fallback_key, {3: 900, 4: 1200, 5: 1800})

    base = tier_prices.get(proc_tier, tier_prices.get(3, 900))

    # RAM adjustment
    ram_adj = RAM_PREMIUM.get(ram_gb, 0)
    if ram_gb not in RAM_PREMIUM:
        # Interpolate
        if ram_gb < 8:
            ram_adj = -100
        elif ram_gb > 64:
            ram_adj = 800

    # Storage adjustment
    stor_adj = STORAGE_PREMIUM.get(storage_gb, 0)
    if storage_gb not in STORAGE_PREMIUM:
        if storage_gb < 128:
            stor_adj = -80
        elif storage_gb > 2000:
            stor_adj = 500

    # Year inflation: newer laptops cost more
    current_year = datetime.now().year
    years_since_release = max(0, current_year - proc_year)
    # But we want the price AT release, so adjust backwards
    # Actually we want forward: newer gen = higher MSRP at launch
    inflation_factor = 1.0 + ANNUAL_PRICE_INFLATION * (proc_year - 2020)

    msrp = (base + ram_adj + stor_adj) * max(0.8, inflation_factor)

    # Apple premium
    if brand == 'Apple':
        msrp *= 1.15

    return round(max(300, msrp), 2)


def estimate_age_months(proc_year: int, scraped_date: str = "2026-02-14") -> int:
    """Estimate age in months from processor release year to scrape date."""
    try:
        scrape = datetime.strptime(scraped_date[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        scrape = datetime.now()

    # Assume laptop was purchased ~6 months after processor release
    purchase_date = datetime(proc_year, 7, 1)  # mid-year
    age_months = max(1, (scrape - purchase_date).days / 30.44)
    return round(age_months)


def ingest_uae_json(json_path: str) -> pd.DataFrame:
    """
    Load UAE marketplace JSON and convert to the LaptopPortfolio format.

    Input JSON format (per item):
      {
        "brand": "Dell",
        "model_series": "Latitude E5450",
        "title": "Dell ... Intel Core i5-5300U 2.3Ghz, 8GB RAM, 256GB SSD...",
        "price_usd": 107.28,
        "condition": "Renewed",
        "processor": "Core i5-5300U",
        "ram_gb": 8,
        "storage_gb": 256,
        "storage_type": "SSD",
        "screen_size": 14,
        "country": "UAE",
        ...
      }

    Output DataFrame columns (matching LaptopPortfolio.xlsx):
      Brand, Model, Start Date, Term, End Date, Processor,
      Display Size, RAM, SDD, Price, RV, Sales Price,
      source_region, condition
    """
    logger.info(f"Loading UAE data from {json_path}")

    with open(json_path, 'r') as f:
        data = json.load(f)

    # Handle both list and dict-with-list formats
    if isinstance(data, dict):
        # Try common wrapper keys
        for key in ['items', 'products', 'laptops', 'data', 'results']:
            if key in data:
                data = data[key]
                break
        else:
            # Single item
            data = [data]

    logger.info(f"Found {len(data)} items in JSON")

    rows = []
    skipped = 0

    for item in data:
        # Skip if no USD price
        price_usd = item.get('price_usd')
        if not price_usd or price_usd <= 0:
            skipped += 1
            continue

        brand = str(item.get('brand', '')).strip()
        if not brand:
            skipped += 1
            continue

        model_series = str(item.get('model_series', item.get('title', ''))).strip()
        processor_str = str(item.get('processor', '')).strip()
        ram_gb = int(item.get('ram_gb', 0) or 0)
        storage_gb = int(item.get('storage_gb', 0) or 0)
        storage_type = str(item.get('storage_type', 'SSD')).upper()
        screen_size = float(item.get('screen_size', 14) or 14)
        condition = str(item.get('condition', 'Renewed'))
        scraped_at = str(item.get('scraped_at', '2026-02-14'))

        # Parse processor info
        proc_info = parse_processor_info(processor_str)

        # Detect model line
        model_line = detect_model_line(brand, model_series)
        if model_line == 'unknown':
            # Try from title
            title = str(item.get('title', ''))
            model_line = detect_model_line(brand, title)

        # Extract model number for tier
        model_number = extract_model_number(model_series)

        # Estimate MSRP (original purchase price)
        msrp = estimate_msrp(
            brand=brand,
            model_line=model_line,
            proc_tier=proc_info['tier'],
            proc_gen=proc_info['gen'],
            ram_gb=ram_gb or 8,
            storage_gb=storage_gb or 256,
            proc_year=proc_info['year'],
        )

        # Estimate age
        age_months = estimate_age_months(proc_info['year'], scraped_at)

        # Compute dates
        try:
            end_date = datetime.strptime(scraped_at[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            end_date = datetime.now()
        start_date = end_date - timedelta(days=age_months * 30.44)

        # Estimate RV (contractual residual value) — not available in marketplace data
        # Use a reasonable default: ~20-25% of MSRP for business laptops
        rv_pct = {
            'workstation': 0.18,
            'business_standard': 0.22,
            'premium': 0.28,
            'sme': 0.18,
            'consumer': 0.15,
            'desktop': 0.12,
            'unknown': 0.20,
        }
        rv = msrp * rv_pct.get(model_line, 0.20)

        # Build row in LaptopPortfolio format
        display_str = f'{screen_size}" FHD'
        ram_str = f'{ram_gb}GB' if ram_gb else '8GB'
        storage_str = f'{storage_gb}GB {storage_type}' if storage_gb else 'No SSD'

        rows.append({
            'Brand': brand,
            'Model': model_series,
            'Serial Number': item.get('asin', ''),
            'Start Date': start_date.strftime('%Y-%m-%d'),
            'Term': age_months,
            'End Date': end_date.strftime('%Y-%m-%d'),
            'Processor': processor_str,
            'Display Size': display_str,
            'RAM': ram_str,
            'SDD': storage_str,
            'Price': msrp,                    # Estimated original purchase price
            'RV': round(rv, 2),               # Estimated contractual RV
            'Sales Price': round(price_usd, 2),  # Actual marketplace resale price
            # Extra columns for analysis
            'source_region': 'UAE',
            'condition': condition,
            'model_line_detected': model_line,
            'processor_gen_parsed': proc_info['gen'],
            'age_months_estimated': age_months,
            'msrp_estimated': True,
        })

    df = pd.DataFrame(rows)
    logger.info(f"Ingested {len(df)} rows, skipped {skipped}")

    # Quality report
    if len(df) > 0:
        logger.info(f"\n{'='*50}")
        logger.info(f"UAE DATA QUALITY REPORT")
        logger.info(f"{'='*50}")
        logger.info(f"Total items:   {len(df)}")
        logger.info(f"Brands:        {df['Brand'].value_counts().to_dict()}")
        logger.info(f"Model lines:   {df['model_line_detected'].value_counts().to_dict()}")
        logger.info(f"Conditions:    {df['condition'].value_counts().to_dict()}")
        logger.info(f"\nPrice (resale USD):")
        logger.info(f"  Mean:   ${df['Sales Price'].mean():.0f}")
        logger.info(f"  Median: ${df['Sales Price'].median():.0f}")
        logger.info(f"  Range:  ${df['Sales Price'].min():.0f} - ${df['Sales Price'].max():.0f}")
        logger.info(f"\nEstimated MSRP (USD):")
        logger.info(f"  Mean:   ${df['Price'].mean():.0f}")
        logger.info(f"  Median: ${df['Price'].median():.0f}")
        logger.info(f"\nEstimated age (months):")
        logger.info(f"  Mean:   {df['age_months_estimated'].mean():.0f}")
        logger.info(f"  Median: {df['age_months_estimated'].median():.0f}")
        logger.info(f"  Range:  {df['age_months_estimated'].min()} - {df['age_months_estimated'].max()}")
        logger.info(f"\nMarket ratio (resale/MSRP):")
        ratios = df['Sales Price'] / df['Price']
        logger.info(f"  Mean:   {ratios.mean():.3f} ({ratios.mean()*100:.1f}%)")
        logger.info(f"  Median: {ratios.median():.3f} ({ratios.median()*100:.1f}%)")
        logger.info(f"  Range:  {ratios.min():.3f} - {ratios.max():.3f}")

        # Flag suspiciously high ratios (resale > MSRP = estimation problem)
        high_ratio = (ratios > 0.80).sum()
        if high_ratio > 0:
            logger.warning(f"  {high_ratio} items have resale > 80% of estimated MSRP — MSRP may be underestimated")

    return df


def save_as_portfolio(df: pd.DataFrame, output_path: str):
    """Save ingested data in the same Excel format as LaptopPortfolio.xlsx."""
    # Keep only the portfolio columns
    portfolio_cols = [
        'Brand', 'Model', 'Serial Number', 'Start Date', 'Term',
        'End Date', 'Processor', 'Display Size', 'RAM', 'SDD',
        'Price', 'RV', 'Sales Price',
    ]
    extra_cols = ['source_region', 'condition']

    out_cols = [c for c in portfolio_cols + extra_cols if c in df.columns]
    df_out = df[out_cols]

    if output_path.endswith('.xlsx'):
        df_out.to_excel(output_path, index=False, engine='openpyxl')
    else:
        df_out.to_csv(output_path, index=False)

    logger.info(f"Saved {len(df_out)} rows to {output_path}")


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python ingest_uae.py <path_to_uae_json> [output_path]")
        print("  output_path defaults to data/UAE_LaptopPortfolio.xlsx")
        sys.exit(1)

    json_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(__file__), '..', 'data', 'UAE_LaptopPortfolio.xlsx'
    )

    df = ingest_uae_json(json_path)
    save_as_portfolio(df, output_path)
