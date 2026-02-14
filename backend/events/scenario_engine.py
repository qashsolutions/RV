"""
Scenario engine: computes adjusted prediction ranges based on
active market events + live sentiment.

This module is used by both:
  - The backend (to write adjusted predictions to Supabase)
  - The frontend (via a static JSON export of active scenarios)
"""

import json
import logging
import math
import os
from datetime import date, timedelta
from typing import List, Optional

logger = logging.getLogger(__name__)


def compute_event_decay(event: dict, as_of: date | None = None) -> float:
    """
    Compute the decay multiplier for an event based on time since effective_from.
    Returns 1.0 at effective_from, decays exponentially toward 0.

    Half-life = decay_months (default 6).
    """
    as_of = as_of or date.today()

    effective_from = event.get("effective_from")
    if not effective_from:
        return 1.0

    if isinstance(effective_from, str):
        effective_from = date.fromisoformat(effective_from)

    days_elapsed = (as_of - effective_from).days
    if days_elapsed < 0:
        return 0.0  # event hasn't started yet

    decay_months = event.get("decay_months", 6)
    half_life_days = decay_months * 30.44  # avg days per month

    return math.exp(-0.693 * days_elapsed / half_life_days)


def compute_scenario_adjustment(
    active_events: List[dict],
    brand: str = "Dell",
    segment: str = "business_standard",
    sentiment_score: float = 0.0,
    sentiment_confidence: float = 0.5,
    as_of: date | None = None,
) -> dict:
    """
    Compute the net impact of all active events + sentiment on a prediction.

    Returns:
        {
            "adjustment_low_pct":  float,  # worst-case total % impact
            "adjustment_high_pct": float,  # best-case total % impact
            "adjustment_mid_pct":  float,  # expected (midpoint weighted by confidence)
            "combined_confidence": float,  # overall confidence in the adjustment
            "event_details": list,         # per-event breakdown
            "sentiment_contrib":   float,  # sentiment component of adjustment
        }
    """
    as_of = as_of or date.today()
    brand_lower = brand.lower()

    total_low = 0.0
    total_high = 0.0
    total_weighted_mid = 0.0
    total_weight = 0.0
    details = []

    for event in active_events:
        # Filter: does this event affect this brand/segment?
        affected_brands = [b.lower() for b in event.get("affected_brands", [])]
        affected_segments = event.get("affected_segments", [])

        if affected_brands and brand_lower not in affected_brands:
            continue
        if affected_segments and segment not in affected_segments:
            continue

        # Compute decay
        decay = compute_event_decay(event, as_of)
        if decay < 0.05:
            continue  # negligible impact

        impact_low = event["impact_low_pct"] * decay
        impact_high = event["impact_high_pct"] * decay
        confidence = event.get("impact_confidence", 0.7)
        mid = (impact_low + impact_high) / 2

        total_low += impact_low
        total_high += impact_high
        total_weighted_mid += mid * confidence
        total_weight += confidence

        details.append({
            "event_id": event.get("id", ""),
            "title": event.get("title", ""),
            "category": event.get("category", ""),
            "impact_low_pct": round(impact_low, 2),
            "impact_high_pct": round(impact_high, 2),
            "confidence": confidence,
            "decay": round(decay, 3),
        })

    # Sentiment contribution: ±3% max, scaled by sentiment score and confidence
    sentiment_contrib = sentiment_score * sentiment_confidence * 3.0  # max ±3%
    total_low += sentiment_contrib if sentiment_contrib < 0 else 0
    total_high += sentiment_contrib if sentiment_contrib > 0 else 0
    total_weighted_mid += sentiment_contrib * sentiment_confidence
    total_weight += sentiment_confidence

    # Combined confidence
    combined_confidence = total_weight / (len(details) + 1) if details else sentiment_confidence

    adjustment_mid = total_weighted_mid / total_weight if total_weight > 0 else 0.0

    return {
        "adjustment_low_pct": round(total_low, 2),
        "adjustment_high_pct": round(total_high, 2),
        "adjustment_mid_pct": round(adjustment_mid, 2),
        "combined_confidence": round(combined_confidence, 4),
        "event_details": details,
        "sentiment_contrib": round(sentiment_contrib, 4),
    }


def export_active_scenarios():
    """
    Fetch active events from Supabase and export a static JSON
    for the frontend to consume.
    """
    from backend.db.client import get_client
    db = get_client()

    # Get active/confirmed events
    result = db.table("market_events") \
        .select("*") \
        .in_("status", ["active", "confirmed", "detected"]) \
        .execute()

    events = result.data or []

    # Get latest sentiment
    sentiment_result = db.table("sentiment_scores") \
        .select("*") \
        .eq("brand", "dell") \
        .eq("source", "combined") \
        .order("scored_date", desc=True) \
        .limit(1) \
        .execute()

    sentiment = sentiment_result.data[0] if sentiment_result.data else {
        "score": 0.0, "confidence": 0.5, "sample_headlines": []
    }

    # Compute scenario for common segments
    scenarios = {}
    for segment in ["business_standard", "workstation", "premium", "sme", "consumer"]:
        scenarios[segment] = compute_scenario_adjustment(
            active_events=events,
            brand="Dell",
            segment=segment,
            sentiment_score=sentiment.get("score", 0.0),
            sentiment_confidence=sentiment.get("confidence", 0.5),
        )

    # Write to static JSON
    output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "public", "data")
    os.makedirs(output_dir, exist_ok=True)

    payload = {
        "updated": date.today().isoformat(),
        "sentiment": {
            "score": sentiment.get("score", 0.0),
            "confidence": sentiment.get("confidence", 0.5),
            "headlines": sentiment.get("sample_headlines", []),
        },
        "active_events": [
            {
                "id": e.get("id"),
                "title": e.get("title"),
                "category": e.get("category"),
                "status": e.get("status"),
                "impact_low_pct": e.get("impact_low_pct"),
                "impact_high_pct": e.get("impact_high_pct"),
                "impact_confidence": e.get("impact_confidence"),
                "effective_from": e.get("effective_from"),
                "decay_months": e.get("decay_months"),
                "affected_brands": e.get("affected_brands", []),
                "affected_segments": e.get("affected_segments", []),
            }
            for e in events
        ],
        "scenarios": scenarios,
    }

    path = os.path.join(output_dir, "active_scenarios.json")
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)

    logger.info(f"Exported {len(events)} active events and scenarios to {path}")
    return payload
