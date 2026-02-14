"""
Shared configuration for all backend pipelines.
Reads from environment variables (set via GitHub Actions secrets or .env file).
"""

import os
from dotenv import load_dotenv

load_dotenv()

# -- Supabase --
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")  # service_role key (bypasses RLS)
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")        # for frontend/public reads

# -- FRED --
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
FRED_SERIES = {
    "cpi_index":           "SGPCPIALLMINMEI",   # Singapore CPI
    "consumer_sentiment":  "DEXSIUS",            # USD/SGD exchange rate
    "fed_funds_rate":      "PCU33443344",        # Semiconductor PPI
}

# -- News sources for sentiment --
NEWS_RSS_FEEDS = [
    "https://news.google.com/rss/search?q=dell+laptop+resale+market&hl=en",
    "https://news.google.com/rss/search?q=used+laptop+prices+enterprise&hl=en",
    "https://news.google.com/rss/search?q=ASEAN+IT+equipment+leasing&hl=en",
    "https://news.google.com/rss/search?q=laptop+depreciation+value&hl=en",
]

# -- Sentiment model --
SENTIMENT_MODEL = "ProsusAI/finbert"  # Financial domain BERT
SENTIMENT_BATCH_SIZE = 16
MAX_ARTICLES_PER_RUN = 50

# -- Model paths --
MODEL_ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "models")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
