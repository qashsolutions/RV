"""
Feature engineering for laptop residual value prediction.
Adapted specifically for the LaptopPortfolio.xlsx data format.

Columns in source data:
  S/No, Brand, Model, Serial Number, Start Date, Term, End Date,
  Processor, Display Size, RAM, SDD, Price, RV, Sales Price
"""

import re
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import json
import os


# ===== BRAND MAPPINGS =====

BRAND_TIER_MAP = {
    'Apple': 'Premium', 'Microsoft': 'Premium',
    'Lenovo': 'Business', 'Dell': 'Business', 'HP': 'Business',
    'Fujitsu': 'Business', 'Panasonic': 'Business',
    'ASUS': 'Mid', 'Acer': 'Mid', 'MSI': 'Mid', 'Samsung': 'Mid',
    'LG': 'Mid', 'Toshiba': 'Mid', 'Dynabook': 'Mid',
    'Huawei': 'Economy', 'Xiaomi': 'Economy', 'Honor': 'Economy',
}
BRAND_TIER_ENCODING = {'Premium': 4, 'Business': 3, 'Mid': 2, 'Economy': 1, 'Unknown': 2}

BRAND_RETENTION = {
    'Apple': 1.15, 'Microsoft': 1.05,
    'Lenovo': 1.00, 'Dell': 0.98, 'HP': 0.97,
    'Fujitsu': 0.95, 'Panasonic': 0.96,
    'ASUS': 0.92, 'Acer': 0.88, 'MSI': 0.90,
    'Samsung': 0.91, 'LG': 0.89,
    'Huawei': 0.80, 'Xiaomi': 0.78,
}

# ===== MODEL LINE MAPPINGS (Dell-specific since data is 99.6% Dell) =====

MODEL_LINE_MAP = {
    'latitude': 'business_standard',
    'precision': 'workstation',
    'inspiron': 'consumer',
    'xps': 'premium',
    'vostro': 'sme',
    'optiplex': 'desktop',
    'thinkpad': 'business_standard',
    'elitebook': 'business_standard',
    'probook': 'sme',
    'zbook': 'workstation',
    'macbook': 'premium',
    'surface': 'premium',
}

MODEL_LINE_ENCODING = {
    'workstation': 5, 'premium': 4, 'business_standard': 3,
    'sme': 2, 'consumer': 1, 'desktop': 1, 'unknown': 2,
}


def parse_ram(val) -> int:
    """Parse RAM string to integer GB. Handles '16GB', '16', '32GB', etc."""
    if pd.isna(val):
        return 16
    s = str(val).strip().upper().replace('GB', '').replace(' ', '')
    try:
        return int(float(s))
    except ValueError:
        return 16


def parse_storage(val) -> tuple:
    """Parse storage string to (size_gb, has_ssd). Handles '512GB', 'No SSD', '1TB', '1TB + 512GB', etc."""
    if pd.isna(val):
        return 512, True
    s = str(val).strip().upper()

    if s in ('NO SSD', 'XXX', ''):
        return 0, False

    # Handle combined: "1TB + 512GB"
    total = 0
    for part in re.split(r'[+&,]', s):
        part = part.strip()
        if 'TB' in part:
            num = re.search(r'(\d+)', part)
            if num:
                total += int(num.group(1)) * 1000
        elif 'GB' in part or part.isdigit():
            num = re.search(r'(\d+)', part)
            if num:
                total += int(num.group(1))

    if total == 0:
        # Try bare number
        num = re.search(r'(\d+)', s)
        if num:
            total = int(num.group(1))
            # If small number, it might be TB
            if total <= 4:
                total *= 1000

    return max(total, 0), total > 0


def parse_display_size(val) -> float:
    """Parse display size string to float inches. Handles '14\" FHD', '13.3', '15.6\" FHD', etc."""
    if pd.isna(val):
        return 14.0
    s = str(val).strip()
    match = re.search(r'(\d+\.?\d*)', s)
    if match:
        return float(match.group(1))
    return 14.0


def parse_processor_gen(val) -> int:
    """Extract processor generation from strings like 'Core i7 - 11 Gen', 'Intel Core i7-1185G7', etc."""
    if pd.isna(val):
        return 0
    s = str(val).strip()

    # Pattern: "Core i7 - 11 Gen" or "Core i5 - 10 Gen"
    match = re.search(r'(\d+)\s*(?:th\s*)?Gen', s, re.IGNORECASE)
    if match:
        return int(match.group(1))

    # Pattern: "i7-1185G7" -> gen 11, "i5-10310U" -> gen 10
    match = re.search(r'i[3579]-(\d{2})\d{2}', s)
    if match:
        return int(match.group(1))

    match = re.search(r'i[3579]-(\d)\d{3}', s)
    if match:
        return int(match.group(1))

    # Pattern: "W-10855M" -> Xeon gen 10
    match = re.search(r'W-(\d{2})\d{3}', s)
    if match:
        return int(match.group(1))

    # Pattern: "Xeon" without generation
    if 'xeon' in s.lower():
        return 10  # Default Xeon to gen 10 for this dataset

    return 0


def parse_processor_tier(val) -> int:
    """Extract processor tier: i9=5, Xeon=5, i7=4, i5=3, i3=2, other=1."""
    if pd.isna(val):
        return 3
    s = str(val).lower()
    if 'xeon' in s or 'i9' in s:
        return 5
    if 'i7' in s:
        return 4
    if 'i5' in s:
        return 3
    if 'i3' in s:
        return 2
    return 1


def extract_model_line(model_str: str) -> str:
    """Extract product line from model string."""
    if pd.isna(model_str):
        return 'unknown'
    s = model_str.lower().strip()
    for keyword, line in MODEL_LINE_MAP.items():
        if keyword in s:
            return line
    return 'unknown'


def engineer_features(df: pd.DataFrame, is_training: bool = True) -> Tuple[pd.DataFrame, Dict]:
    """
    Feature engineering tailored to LaptopPortfolio.xlsx format.

    Target: predicts retention_ratio = Sales Price / Price (actual market value ratio)
    Fallback target: RV / Price (contractual residual value ratio)
    """
    df = df.copy()

    # ---- Standardize column names ----
    col_map = {}
    for c in df.columns:
        cl = c.strip().lower().replace(' ', '_')
        col_map[c] = cl
    df = df.rename(columns=col_map)

    # ---- Parse dates and compute age ----
    for dc in ['start_date', 'end_date']:
        if dc in df.columns:
            df[dc] = pd.to_datetime(df[dc], errors='coerce')

    if 'start_date' in df.columns and 'end_date' in df.columns:
        df['lease_duration_months'] = ((df['end_date'] - df['start_date']).dt.days / 30.44).round(0)
        # Age at end of lease (years)
        df['age_years'] = df['lease_duration_months'] / 12.0
    elif 'term' in df.columns:
        df['lease_duration_months'] = pd.to_numeric(df['term'], errors='coerce').fillna(36)
        df['age_years'] = df['lease_duration_months'] / 12.0

    df['age_squared'] = df['age_years'] ** 2

    # ---- Brand features ----
    if 'brand' in df.columns:
        df['brand_clean'] = df['brand'].str.strip().str.replace(r'\s*\(.*\)', '', regex=True).str.title()
        df['brand_tier'] = df['brand_clean'].map(BRAND_TIER_MAP).fillna('Business')
        df['brand_tier_encoded'] = df['brand_tier'].map(BRAND_TIER_ENCODING).fillna(3)
        df['brand_retention'] = df['brand_clean'].map(BRAND_RETENTION).fillna(0.90)

    # ---- Model line features ----
    if 'model' in df.columns:
        df['model_line'] = df['model'].apply(extract_model_line)
        df['model_line_encoded'] = df['model_line'].map(MODEL_LINE_ENCODING).fillna(2)

        # Extract model number (e.g. Latitude 7320 -> 7320)
        df['model_number'] = df['model'].str.extract(r'(\d{4})', expand=False).astype(float)
        # Higher model numbers generally = higher spec tier within a line
        df['model_tier'] = (df['model_number'] / 1000).fillna(5).clip(1, 9).round(0)

    # ---- Processor features ----
    if 'processor' in df.columns:
        df['processor_gen'] = df['processor'].apply(parse_processor_gen)
        df['processor_tier'] = df['processor'].apply(parse_processor_tier)
        df['is_xeon'] = df['processor'].str.lower().str.contains('xeon', na=False).astype(int)

    # ---- RAM features ----
    if 'ram' in df.columns:
        df['ram_gb'] = df['ram'].apply(parse_ram)
        df['ram_log'] = np.log2(df['ram_gb'].clip(lower=1))

    # ---- Storage features ----
    if 'sdd' in df.columns:
        parsed = df['sdd'].apply(parse_storage)
        df['storage_gb'] = parsed.apply(lambda x: x[0])
        df['has_ssd'] = parsed.apply(lambda x: int(x[1]))
        df['storage_log'] = np.log2(df['storage_gb'].clip(lower=1))

    # ---- Display size ----
    if 'display_size' in df.columns:
        df['screen_inches'] = df['display_size'].apply(parse_display_size)
        # Size buckets
        df['screen_bucket'] = pd.cut(
            df['screen_inches'], bins=[0, 12.5, 13.5, 14.5, 16, 20],
            labels=[1, 2, 3, 4, 5]
        ).astype(float).fillna(3)
        df['is_touch'] = df['display_size'].str.lower().str.contains('touch', na=False).astype(int)

    # ---- Price features ----
    if 'price' in df.columns:
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
        df['price_log'] = np.log1p(df['price'].fillna(0))
        df['price_tier'] = pd.cut(
            df['price'].fillna(0),
            bins=[0, 1000, 1500, 2000, 3000, 10000],
            labels=[1, 2, 3, 4, 5]
        ).astype(float).fillna(2)

    # ---- Spec composite score ----
    spec_parts = []
    if 'ram_gb' in df.columns:
        spec_parts.append(df['ram_gb'] / 64.0)
    if 'storage_gb' in df.columns:
        spec_parts.append(df['storage_gb'] / 2000.0)
    if 'processor_gen' in df.columns:
        spec_parts.append(df['processor_gen'] / 13.0)
    if 'processor_tier' in df.columns:
        spec_parts.append(df['processor_tier'] / 5.0)
    if spec_parts:
        df['spec_score'] = sum(spec_parts) / len(spec_parts)

    # ---- Target variables ----
    if is_training:
        if 'price' in df.columns and 'rv' in df.columns:
            df['rv'] = pd.to_numeric(df['rv'], errors='coerce')
            df['rv_ratio'] = df['rv'] / df['price'].replace(0, np.nan)
            df['rv_ratio'] = df['rv_ratio'].clip(0, 1.0)

        if 'price' in df.columns and 'sales_price' in df.columns:
            df['sales_price'] = pd.to_numeric(df['sales_price'], errors='coerce')
            df['market_ratio'] = df['sales_price'] / df['price'].replace(0, np.nan)
            df['market_ratio'] = df['market_ratio'].clip(0, 1.0)

            # Gain/loss vs RV: positive = sold above RV, negative = loss
            if 'rv' in df.columns:
                df['rv_vs_market'] = df['sales_price'] - df['rv']
                df['rv_accuracy'] = df['sales_price'] / df['rv'].replace(0, np.nan)

    # ---- Metadata for frontend ----
    metadata = {
        'brand_tier_map': BRAND_TIER_MAP,
        'brand_tier_encoding': BRAND_TIER_ENCODING,
        'brand_retention': BRAND_RETENTION,
        'model_line_map': MODEL_LINE_MAP,
        'model_line_encoding': MODEL_LINE_ENCODING,
    }

    return df, metadata


def get_feature_columns() -> List[str]:
    """Feature columns for ML model input."""
    return [
        'age_years',
        'age_squared',
        'lease_duration_months',
        'brand_tier_encoded',
        'brand_retention',
        'model_line_encoded',
        'model_tier',
        'processor_gen',
        'processor_tier',
        'is_xeon',
        'ram_gb',
        'ram_log',
        'storage_gb',
        'storage_log',
        'has_ssd',
        'screen_inches',
        'screen_bucket',
        'price_log',
        'price_tier',
        'spec_score',
    ]


def get_target_column() -> str:
    """Primary target: actual market retention ratio."""
    return 'market_ratio'


def get_fallback_target() -> str:
    """Fallback target when sales price unavailable: contractual RV ratio."""
    return 'rv_ratio'


def save_metadata(metadata: Dict, output_dir: str):
    """Save feature encoding metadata for frontend JS."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, 'feature_metadata.json')
    with open(path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"Feature metadata saved to {path}")


def load_data(filepath: str) -> pd.DataFrame:
    """Load data from Excel or CSV."""
    if filepath.endswith(('.xlsx', '.xls')):
        return pd.read_excel(filepath, engine='openpyxl')
    elif filepath.endswith('.csv'):
        return pd.read_csv(filepath)
    raise ValueError(f"Unsupported format: {filepath}")
