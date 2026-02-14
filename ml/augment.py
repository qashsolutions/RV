"""
Synthetic data augmentation for small datasets.
Uses statistical bootstrapping and domain-knowledge priors for ASEAN laptop market.
"""

import pandas as pd
import numpy as np
from typing import Optional


# Depreciation curve priors by brand tier (annual retention %)
DEPRECIATION_PRIORS = {
    'Premium': [0.82, 0.70, 0.60, 0.52, 0.45],     # Apple, Microsoft
    'Business': [0.78, 0.64, 0.53, 0.44, 0.37],     # Lenovo, Dell, HP
    'Mid': [0.72, 0.57, 0.45, 0.36, 0.29],          # ASUS, Acer, MSI
    'Economy': [0.65, 0.48, 0.36, 0.27, 0.21],      # Huawei, Xiaomi
}


def augment_data(df: pd.DataFrame, target_rows: int = 500,
                 noise_level: float = 0.05) -> pd.DataFrame:
    """
    Augment a small dataset using bootstrapping with noise.

    Args:
        df: Original dataframe
        target_rows: Desired total number of rows
        noise_level: Standard deviation of noise added to numeric features

    Returns:
        Augmented dataframe
    """
    if len(df) >= target_rows:
        return df

    augmented_rows = []
    rows_needed = target_rows - len(df)

    for _ in range(rows_needed):
        base_row = df.sample(n=1).iloc[0].copy()

        for col in df.select_dtypes(include=[np.number]).columns:
            if col in base_row and pd.notna(base_row[col]) and base_row[col] != 0:
                noise = np.random.normal(0, noise_level * abs(base_row[col]))
                base_row[col] = max(0, base_row[col] + noise)

        int_cols = ['year_manufactured', 'ram_gb', 'storage_gb']
        for col in int_cols:
            if col in base_row and pd.notna(base_row[col]):
                base_row[col] = int(round(base_row[col]))

        augmented_rows.append(base_row)

    augmented_df = pd.DataFrame(augmented_rows)
    result = pd.concat([df, augmented_df], ignore_index=True)

    print(f"Augmented: {len(df)} -> {len(result)} rows ({rows_needed} synthetic)")
    return result


def generate_synthetic_dataset(n_samples: int = 1000, seed: int = 42) -> pd.DataFrame:
    """
    Generate a fully synthetic laptop dataset using domain knowledge priors.
    Useful for initial testing before real data is available.
    """
    np.random.seed(seed)

    brands_by_tier = {
        'Premium': ['Apple', 'Microsoft'],
        'Business': ['Lenovo', 'Dell', 'HP', 'Fujitsu'],
        'Mid': ['ASUS', 'Acer', 'MSI', 'Samsung', 'LG'],
        'Economy': ['Huawei', 'Xiaomi', 'Honor'],
    }

    categories = ['Business', 'Ultrabook', 'Workstation', 'Gaming', 'Convertible', 'Budget']
    conditions = ['Excellent', 'Good', 'Fair', 'Poor']
    countries = ['Malaysia', 'Singapore', 'Thailand', 'Indonesia', 'Vietnam', 'Philippines']
    country_probs = [0.35, 0.15, 0.15, 0.15, 0.10, 0.10]

    records = []
    for _ in range(n_samples):
        tier = np.random.choice(list(brands_by_tier.keys()), p=[0.15, 0.40, 0.30, 0.15])
        brand = np.random.choice(brands_by_tier[tier])
        category = np.random.choice(categories, p=[0.35, 0.20, 0.10, 0.15, 0.10, 0.10])
        country = np.random.choice(countries, p=country_probs)

        # Age (1-5 years typical for B2B leased laptops)
        age = np.random.choice([1, 2, 3, 4, 5], p=[0.15, 0.25, 0.30, 0.20, 0.10])
        sale_year = np.random.randint(2021, 2026)
        mfg_year = sale_year - age

        # Specs
        ram = np.random.choice([4, 8, 16, 32, 64], p=[0.05, 0.30, 0.40, 0.20, 0.05])
        storage = np.random.choice([128, 256, 512, 1024, 2048], p=[0.05, 0.25, 0.40, 0.25, 0.05])
        screen = np.random.choice([13.3, 14.0, 15.6, 17.3], p=[0.25, 0.35, 0.30, 0.10])

        # Processor
        if brand == 'Apple':
            cpu = f'Apple M{np.random.choice([1, 2, 3])}'
            cpu_brand = 'Apple'
        elif np.random.random() < 0.75:
            gen = max(8, min(14, mfg_year - 2008))
            cpu = f'Intel Core i{np.random.choice([5, 7])}-{gen}{np.random.randint(100, 999)}'
            cpu_brand = 'Intel'
        else:
            gen = max(3, min(8, mfg_year - 2017))
            cpu = f'AMD Ryzen {np.random.choice([5, 7])} {gen}{np.random.randint(100, 999)}'
            cpu_brand = 'AMD'

        # Purchase price
        base_price_map = {
            'Premium': np.random.uniform(1200, 3500),
            'Business': np.random.uniform(800, 2500),
            'Mid': np.random.uniform(500, 1500),
            'Economy': np.random.uniform(300, 900),
        }
        purchase_price = base_price_map[tier]
        if category == 'Gaming':
            purchase_price *= 1.3
        elif category == 'Workstation':
            purchase_price *= 1.4

        # Condition (correlated with age)
        if age <= 1:
            cond_probs = [0.40, 0.45, 0.12, 0.03]
        elif age <= 3:
            cond_probs = [0.10, 0.50, 0.30, 0.10]
        else:
            cond_probs = [0.03, 0.25, 0.45, 0.27]
        condition = np.random.choice(conditions, p=cond_probs)

        # Residual value calculation
        dep_curve = DEPRECIATION_PRIORS[tier]
        base_retention = dep_curve[min(age - 1, len(dep_curve) - 1)]

        # Adjustments
        condition_adj = {'Excellent': 1.08, 'Good': 1.0, 'Fair': 0.88, 'Poor': 0.72}
        base_retention *= condition_adj[condition]

        # Spec premium (higher specs retain more)
        if ram >= 16:
            base_retention *= 1.03
        if storage >= 512:
            base_retention *= 1.02

        # Noise
        base_retention *= np.random.normal(1.0, 0.04)
        base_retention = max(0.05, min(1.0, base_retention))

        sale_price = purchase_price * base_retention

        records.append({
            'brand': brand,
            'model': f'{brand}-{np.random.randint(1000, 9999)}',
            'category': category,
            'year_manufactured': mfg_year,
            'purchase_price': round(purchase_price, 2),
            'sale_price': round(sale_price, 2),
            'sale_date': f'{sale_year}-{np.random.randint(1, 13):02d}-{np.random.randint(1, 29):02d}',
            'processor': cpu,
            'processor_brand': cpu_brand,
            'ram_gb': ram,
            'storage_gb': storage,
            'storage_type': 'SSD' if np.random.random() < 0.85 else 'HDD',
            'screen_size': screen,
            'condition': condition,
            'country': country,
            'lease_duration_months': np.random.choice([12, 24, 36, 48], p=[0.10, 0.25, 0.45, 0.20]),
        })

    return pd.DataFrame(records)


if __name__ == '__main__':
    df = generate_synthetic_dataset(1000)
    import os
    os.makedirs('../data', exist_ok=True)
    df.to_excel('../data/synthetic_laptop_data.xlsx', index=False)
    print(f"Generated synthetic dataset: {df.shape}")
    print(f"\nSample:\n{df.head()}")
    print(f"\nBrand distribution:\n{df['brand'].value_counts()}")
    print(f"\nCountry distribution:\n{df['country'].value_counts()}")
