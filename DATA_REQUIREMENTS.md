# Data Requirements

## Overview

This document specifies the data format, required fields, and optional enrichment fields for training the residual value prediction model. Upload your Excel (.xlsx) file to the `data/` directory.

## Required Core Fields

These are the minimum fields needed to train a baseline model:

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| `equipment_type` | string | "Excavator" | Category of equipment (Excavator, Loader, Crane, Bulldozer, etc.) |
| `brand` | string | "Caterpillar" | Manufacturer/OEM |
| `model` | string | "320F" | Model designation |
| `year_manufactured` | int | 2018 | Year of manufacture |
| `purchase_price_usd` | float | 85000.00 | Original purchase price (USD or MYR — specify) |
| `sale_price_usd` | float | 42000.00 | Actual resale/transaction price |
| `sale_date` | date | 2023-06-15 | Date of resale transaction |
| `operating_hours` | int | 6500 | Total hours on the meter at time of sale |
| `condition` | string | "Good" | Equipment condition (Excellent/Good/Fair/Poor) |
| `country` | string | "Malaysia" | Country of sale/operation |

## Highly Recommended Fields

These significantly improve prediction accuracy:

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| `brand_origin` | string | "Japan" | Country of brand origin (Japan/China/Europe/USA/Korea) |
| `equipment_subcategory` | string | "Hydraulic Excavator" | More specific type |
| `weight_tons` | float | 20.5 | Operating weight |
| `engine_power_hp` | int | 148 | Engine power |
| `purchase_date` | date | 2018-03-01 | Original purchase date |
| `region` | string | "Peninsular Malaysia" | Sub-country region |
| `usage_intensity` | string | "Heavy" | How intensively used (Light/Medium/Heavy) |
| `maintenance_record` | string | "Full" | Maintenance history (Full/Partial/None) |
| `attachment_count` | int | 3 | Number of attachments included |

## Optional Enrichment Fields

These add further predictive power and support Phase II:

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| `climate_zone` | string | "Tropical Wet" | Operating climate zone |
| `fuel_type` | string | "Diesel" | Fuel/power type |
| `transmission_type` | string | "Hydraulic" | Transmission type |
| `tire_or_track` | string | "Track" | Undercarriage type |
| `previous_owners` | int | 2 | Number of previous owners |
| `accident_history` | bool | false | Any major incidents |
| `last_service_date` | date | 2023-01-15 | Most recent service |
| `dealer_vs_private` | string | "Dealer" | Channel of sale |
| `financing_type` | string | "Lease" | How the equipment was financed |
| `lessee_industry` | string | "Road Construction" | End-user industry |
| `lessee_company_size` | string | "Medium" | Lessee company size (Phase II credit scoring foundation) |

## Data Volume Guidelines

| Scenario | Min Rows | Expected Accuracy (R²) |
|----------|----------|----------------------|
| MVP / Prototype | 200+ | 0.70 - 0.80 |
| Production-ready | 2,000+ | 0.85 - 0.93 |
| Market-leading | 10,000+ | 0.90 - 0.95+ |

## Currency Handling

- Preferred: All prices in **USD**
- If prices are in **MYR**, include a column `currency` with value "MYR" — the pipeline will auto-convert
- Mixed currencies are supported if `currency` column is present

## Data Quality Notes

1. **No cleaning needed** — The pipeline handles missing values, outliers, and normalization
2. **Duplicates OK** — Deduplication is automatic
3. **Mixed formats OK** — Date parsing is flexible (YYYY-MM-DD, DD/MM/YYYY, etc.)
4. **Column names** — Can be slightly different (the pipeline does fuzzy matching on column headers)

## File Upload

Place your Excel file at:
```
data/equipment_data.xlsx
```

Or any `.xlsx` file in the `data/` directory — the pipeline auto-detects all Excel files.

## Synthetic Data Augmentation

If your dataset is small (<500 rows), the pipeline can generate synthetic training samples using:
- Statistical bootstrapping from your real data distributions
- ASEAN market knowledge priors (brand depreciation curves, climate factors)
- This is toggled with `--augment` flag during training
