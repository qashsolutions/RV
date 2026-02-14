"""
Daily sentiment pipeline entry point.
Called by GitHub Actions on a cron schedule.

Flow:
  1. Scrape recent news articles
  2. Run FinBERT sentiment analysis
  3. Write daily score to Supabase
"""

import json
import logging
import sys
from datetime import date

from backend.db.client import get_client
from backend.sentiment.scraper import fetch_rss_articles
from backend.sentiment.analyzer import SentimentAnalyzer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_sentiment_pipeline(target_date: date | None = None):
    today = target_date or date.today()
    logger.info(f"=== Sentiment pipeline for {today} ===")

    # 1. Scrape
    logger.info("Step 1: Scraping news articles...")
    articles = fetch_rss_articles(max_age_days=3)
    logger.info(f"  Found {len(articles)} articles")

    if not articles:
        logger.warning("No articles found. Writing neutral score.")
        result = {"score": 0.0, "confidence": 0.0, "article_count": 0,
                  "sample_headlines": [], "per_article": []}
    else:
        # 2. Analyze
        logger.info("Step 2: Running FinBERT sentiment analysis...")
        analyzer = SentimentAnalyzer()
        result = analyzer.analyze_articles(articles)
        logger.info(f"  Score: {result['score']:+.4f} (confidence: {result['confidence']:.4f})")

    # 3. Write to Supabase
    logger.info("Step 3: Writing to Supabase...")
    db = get_client()

    row = {
        "scored_date": today.isoformat(),
        "brand": "dell",
        "source": "combined",
        "score": result["score"],
        "confidence": result["confidence"],
        "article_count": result["article_count"],
        "sample_headlines": result["sample_headlines"],
        "raw_payload": json.loads(json.dumps(result["per_article"])),
    }

    # Upsert: update if same date+brand+source already exists
    db.table("sentiment_scores").upsert(
        row,
        on_conflict="scored_date,brand,source",
    ).execute()

    logger.info(f"  Saved sentiment score for {today}: {result['score']:+.4f}")

    # Also write to a static JSON file for the frontend (fallback if Supabase is down)
    _write_latest_json(today, result)

    return result


def _write_latest_json(today: date, result: dict):
    """Write latest sentiment to a JSON file the frontend can fetch from GitHub Pages."""
    import os
    output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "public", "data")
    os.makedirs(output_dir, exist_ok=True)

    payload = {
        "date": today.isoformat(),
        "sentiment": {
            "score": result["score"],
            "confidence": result["confidence"],
            "article_count": result["article_count"],
            "sample_headlines": result["sample_headlines"],
        },
    }

    path = os.path.join(output_dir, "latest_sentiment.json")
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)

    logger.info(f"  Wrote fallback JSON to {path}")


if __name__ == "__main__":
    run_sentiment_pipeline()
