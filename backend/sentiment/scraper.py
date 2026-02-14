"""
News scraper: fetches articles from RSS feeds related to the
used laptop / IT equipment leasing market.
"""

import logging
from datetime import datetime, timedelta
from typing import List, TypedDict

import feedparser
import requests
from bs4 import BeautifulSoup

from backend.config import NEWS_RSS_FEEDS, MAX_ARTICLES_PER_RUN

logger = logging.getLogger(__name__)


class Article(TypedDict):
    title: str
    summary: str
    url: str
    published: str
    source: str


def fetch_rss_articles(max_age_days: int = 7) -> List[Article]:
    """Fetch recent articles from configured RSS feeds."""
    cutoff = datetime.utcnow() - timedelta(days=max_age_days)
    articles: List[Article] = []

    for feed_url in NEWS_RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                # Parse published date
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    published = datetime(*entry.updated_parsed[:6])

                if published and published < cutoff:
                    continue

                # Extract text
                summary = ""
                if hasattr(entry, "summary"):
                    summary = BeautifulSoup(entry.summary, "html.parser").get_text(strip=True)

                articles.append(Article(
                    title=entry.get("title", ""),
                    summary=summary[:500],
                    url=entry.get("link", ""),
                    published=published.isoformat() if published else "",
                    source=feed.feed.get("title", feed_url),
                ))

                if len(articles) >= MAX_ARTICLES_PER_RUN:
                    return articles

        except Exception as e:
            logger.warning(f"Failed to fetch RSS feed {feed_url}: {e}")
            continue

    logger.info(f"Scraped {len(articles)} articles from {len(NEWS_RSS_FEEDS)} feeds")
    return articles


def extract_article_text(url: str, timeout: int = 10) -> str:
    """Fetch the full text of an article URL (best-effort)."""
    try:
        resp = requests.get(url, timeout=timeout, headers={
            "User-Agent": "EquipValAI/1.0 (research; laptop resale market analysis)"
        })
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove script/style elements
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)
        return text[:2000]  # cap at 2000 chars for model input
    except Exception as e:
        logger.debug(f"Could not extract text from {url}: {e}")
        return ""
