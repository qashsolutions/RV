"""
FRED macro data refresh pipeline.
Fetches latest economic indicators and writes to Supabase + static JSON.

Tracked series:
  - SGPCPIALLMINMEI  → Singapore CPI (inflation proxy for ASEAN)
  - DEXSIUS          → USD/SGD exchange rate (currency risk)
  - PCU33443344      → Semiconductor PPI (component costs)
"""

import json
import logging
import os
from datetime import date, timedelta

import pandas as pd
import requests

from backend.config import FRED_API_KEY, FRED_SERIES, MODEL_ARTIFACTS_DIR
from backend.db.client import get_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


def fetch_fred_series(series_id: str, start_date: str = "2020-01-01") -> pd.DataFrame:
    """Fetch a single FRED series as a DataFrame."""
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": start_date,
        "sort_order": "desc",
        "limit": 120,  # ~10 years of monthly data
    }
    resp = requests.get(FRED_BASE, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    rows = []
    for obs in data.get("observations", []):
        if obs["value"] == ".":
            continue
        rows.append({
            "date": obs["date"],
            "value": float(obs["value"]),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
    return df


def compute_changes(df: pd.DataFrame) -> pd.DataFrame:
    """Add YoY and MoM change columns."""
    df = df.copy()
    df["mom_change"] = df["value"].pct_change()
    df["yoy_change"] = df["value"].pct_change(periods=12)
    return df


def run_fred_refresh():
    """Fetch all tracked FRED series and write to Supabase + JSON."""
    if not FRED_API_KEY:
        logger.warning("FRED_API_KEY not set. Using cached defaults only.")
        return

    logger.info("=== FRED macro data refresh ===")
    db = get_client()

    latest_values = {}

    for feature_name, series_id in FRED_SERIES.items():
        logger.info(f"Fetching {feature_name} ({series_id})...")

        try:
            df = fetch_fred_series(series_id)
            if df.empty:
                logger.warning(f"  No data for {series_id}")
                continue

            df = compute_changes(df)

            # Write all rows to Supabase
            rows = []
            for _, row in df.iterrows():
                rows.append({
                    "indicator_date": row["date"].date().isoformat(),
                    "series_id": series_id,
                    "value": round(float(row["value"]), 4),
                    "yoy_change": round(float(row["yoy_change"]), 6) if pd.notna(row["yoy_change"]) else None,
                    "mom_change": round(float(row["mom_change"]), 6) if pd.notna(row["mom_change"]) else None,
                    "source": "fred",
                })

            # Batch upsert
            db.table("macro_indicators").upsert(
                rows,
                on_conflict="indicator_date,series_id",
            ).execute()

            # Track latest for JSON export
            latest_row = df.iloc[-1]
            latest_values[feature_name] = {
                "value": round(float(latest_row["value"]), 4),
                "date": latest_row["date"].date().isoformat(),
                "yoy_change": round(float(latest_row["yoy_change"]), 6) if pd.notna(latest_row["yoy_change"]) else None,
            }

            logger.info(f"  {feature_name}: {latest_values[feature_name]['value']} "
                         f"(as of {latest_values[feature_name]['date']})")

        except Exception as e:
            logger.error(f"  Failed to fetch {series_id}: {e}")
            continue

    # Write latest values to static JSON for frontend
    _write_macro_json(latest_values)

    # Also update the manifest.json with fresh FRED defaults
    _update_manifest(latest_values)

    logger.info("FRED refresh complete.")
    return latest_values


def _write_macro_json(latest: dict):
    """Write latest macro data to a JSON file for the frontend."""
    output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "public", "data")
    os.makedirs(output_dir, exist_ok=True)

    path = os.path.join(output_dir, "latest_macro.json")
    payload = {
        "updated": date.today().isoformat(),
        "indicators": latest,
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    logger.info(f"  Wrote macro JSON to {path}")


def _update_manifest(latest: dict):
    """Update the model manifest.json with fresh FRED default values."""
    manifest_path = os.path.join(MODEL_ARTIFACTS_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        logger.warning(f"  manifest.json not found at {manifest_path}, skipping update")
        return

    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    # Map feature names to manifest keys
    fred_defaults = manifest.get("fred_defaults", {})

    if "cpi_index" in latest:
        fred_defaults["cpi_index"] = latest["cpi_index"]["value"]
        if latest["cpi_index"]["yoy_change"] is not None:
            fred_defaults["cpi_yoy_change"] = latest["cpi_index"]["yoy_change"]

    if "consumer_sentiment" in latest:
        fred_defaults["consumer_sentiment"] = latest["consumer_sentiment"]["value"]

    if "fed_funds_rate" in latest:
        fred_defaults["fed_funds_rate"] = latest["fed_funds_rate"]["value"]

    # Recompute macro_score: 40% SGD strength + 30% low inflation + 30% low semi costs
    try:
        sgd_rate = fred_defaults.get("consumer_sentiment", 1.34)
        cpi = fred_defaults.get("cpi_index", 117.5)
        semi_ppi = fred_defaults.get("fed_funds_rate", 107.0)

        sgd_strength = max(0, min(1, (1.40 - sgd_rate) / 0.15))  # stronger SGD = higher score
        low_inflation = max(0, min(1, (125 - cpi) / 20))
        low_semi_cost = max(0, min(1, (120 - semi_ppi) / 30))

        fred_defaults["macro_score"] = round(
            0.40 * sgd_strength + 0.30 * low_inflation + 0.30 * low_semi_cost, 4
        )
    except Exception:
        pass

    manifest["fred_defaults"] = fred_defaults
    manifest["fred_updated"] = date.today().isoformat()

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    logger.info(f"  Updated manifest.json with fresh FRED defaults")


if __name__ == "__main__":
    run_fred_refresh()
