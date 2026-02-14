"""
Market event detector.
Scans recent news articles for predefined event patterns
and auto-creates 'detected' events in Supabase.
"""

import logging
import re
from datetime import date
from typing import List, Optional

from backend.db.client import get_client
from backend.sentiment.scraper import Article

logger = logging.getLogger(__name__)

# Event detection rules: (pattern, category, title_template, impact_low, impact_high, confidence)
EVENT_RULES = [
    # Competitor launches
    {
        "patterns": [
            r"apple.*(launch|releas|announc|unveil).*macbook",
            r"macbook.*(launch|releas|announc|new|m\d)",
            r"new macbook.*(pro|air)",
        ],
        "category": "competitor_launch",
        "title": "Apple MacBook launch detected",
        "impact_low": -8.0,
        "impact_high": -3.0,
        "confidence": 0.65,
        "affected_brands": ["Dell", "Lenovo", "HP"],
        "affected_segments": ["premium", "business_standard"],
        "decay_months": 6,
    },
    {
        "patterns": [
            r"lenovo.*(launch|releas|announc|unveil).*thinkpad",
            r"thinkpad.*(new|launch|refresh|next.gen)",
        ],
        "category": "competitor_launch",
        "title": "Lenovo ThinkPad refresh detected",
        "impact_low": -4.0,
        "impact_high": -1.5,
        "confidence": 0.60,
        "affected_brands": ["Dell", "HP"],
        "affected_segments": ["business_standard"],
        "decay_months": 4,
    },
    # Dell discontinuation / refresh
    {
        "patterns": [
            r"dell.*(discontinu|end.of.life|eol|phase.out)",
            r"(latitude|precision|xps|vostro).*(discontinu|end.of.life)",
        ],
        "category": "model_discontinuation",
        "title": "Dell model discontinuation detected",
        "impact_low": -12.0,
        "impact_high": -5.0,
        "confidence": 0.70,
        "affected_brands": ["Dell"],
        "affected_segments": [],
        "decay_months": 12,
    },
    {
        "patterns": [
            r"dell.*(new|launch|refresh|next.gen).*(latitude|precision)",
            r"(latitude|precision).*(new|launch|refresh|next.gen)",
        ],
        "category": "model_discontinuation",
        "title": "Dell Latitude/Precision refresh detected",
        "impact_low": -6.0,
        "impact_high": -2.0,
        "confidence": 0.60,
        "affected_brands": ["Dell"],
        "affected_segments": ["business_standard", "workstation"],
        "decay_months": 6,
    },
    # Supply chain
    {
        "patterns": [
            r"(chip|semiconductor|processor).*(shortage|supply|constrain|scarc)",
            r"(tsmc|intel|amd).*(delay|shortage|supply.issue)",
        ],
        "category": "supply_chain",
        "title": "Semiconductor supply disruption detected",
        "impact_low": 2.0,
        "impact_high": 8.0,
        "confidence": 0.60,
        "affected_brands": [],
        "affected_segments": [],
        "decay_months": 9,
    },
    {
        "patterns": [
            r"(shipping|logistics|port|freight).*(delay|disrupt|crisis|bottleneck)",
            r"(suez|panama|red.sea).*(block|disrupt|delay)",
        ],
        "category": "supply_chain",
        "title": "Logistics disruption detected",
        "impact_low": 1.5,
        "impact_high": 5.0,
        "confidence": 0.55,
        "affected_brands": [],
        "affected_segments": [],
        "decay_months": 4,
    },
    # Macro-economic
    {
        "patterns": [
            r"(recession|downturn|slowdown).*(asean|singapore|global|econom)",
            r"(gdp|growth).*(contract|declin|negative|slow)",
        ],
        "category": "macro_economic",
        "title": "Economic slowdown detected",
        "impact_low": -15.0,
        "impact_high": -8.0,
        "confidence": 0.60,
        "affected_brands": [],
        "affected_segments": [],
        "decay_months": 12,
    },
    # Technology shift
    {
        "patterns": [
            r"(arm|qualcomm|snapdragon).*(windows|laptop|enterprise)",
            r"windows.*(arm|qualcomm|copilot\+?\s*pc)",
        ],
        "category": "technology_shift",
        "title": "ARM-based Windows adoption signal",
        "impact_low": -7.0,
        "impact_high": -2.0,
        "confidence": 0.50,
        "affected_brands": [],
        "affected_segments": [],
        "decay_months": 18,
    },
]


def detect_events(articles: List[Article]) -> List[dict]:
    """
    Scan articles for event patterns. Returns list of detected events
    (not yet written to DB — caller decides whether to persist).
    """
    detected = []
    today = date.today()

    for rule in EVENT_RULES:
        matching_articles = []
        for article in articles:
            text = f"{article['title']} {article['summary']}".lower()
            for pattern in rule["patterns"]:
                if re.search(pattern, text, re.IGNORECASE):
                    matching_articles.append(article)
                    break

        if not matching_articles:
            continue

        # Scale confidence by number of corroborating articles
        base_conf = rule["confidence"]
        boost = min(0.2, len(matching_articles) * 0.05)  # +5% per extra article, max +20%
        adjusted_conf = min(0.95, base_conf + boost)

        headlines = [a["title"] for a in matching_articles[:3]]

        detected.append({
            "title": rule["title"],
            "description": f"Auto-detected from {len(matching_articles)} article(s): {'; '.join(headlines[:2])}",
            "category": rule["category"],
            "status": "detected",
            "impact_low_pct": rule["impact_low"],
            "impact_high_pct": rule["impact_high"],
            "impact_confidence": round(adjusted_conf, 4),
            "affected_brands": rule.get("affected_brands", []),
            "affected_segments": rule.get("affected_segments", []),
            "effective_from": today.isoformat(),
            "decay_months": rule.get("decay_months", 6),
            "source_url": matching_articles[0].get("url", ""),
            "source_type": "news",
        })

    logger.info(f"Detected {len(detected)} events from {len(articles)} articles")
    return detected


def persist_events(events: List[dict], dedup_window_days: int = 30):
    """
    Write detected events to Supabase, skipping duplicates.
    A duplicate = same category + same title within dedup_window_days.
    """
    if not events:
        return

    db = get_client()

    for event in events:
        # Check for recent duplicates
        existing = (
            db.table("market_events")
            .select("id")
            .eq("category", event["category"])
            .eq("title", event["title"])
            .gte("detected_at", f"now() - interval '{dedup_window_days} days'")
            .execute()
        )

        if existing.data:
            logger.info(f"  Skipping duplicate: {event['title']}")
            continue

        db.table("market_events").insert(event).execute()
        logger.info(f"  Persisted event: {event['title']} ({event['category']})")
