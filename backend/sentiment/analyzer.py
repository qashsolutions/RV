"""
Sentiment analyzer using FinBERT (financial domain BERT).
Processes scraped articles and produces a daily sentiment score.
"""

import logging
from datetime import date
from typing import List, Tuple

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from backend.config import SENTIMENT_MODEL, SENTIMENT_BATCH_SIZE
from backend.sentiment.scraper import Article

logger = logging.getLogger(__name__)

# Labels output by FinBERT
LABEL_MAP = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}


class SentimentAnalyzer:
    """Wraps FinBERT for batch inference on news headlines/summaries."""

    def __init__(self):
        logger.info(f"Loading sentiment model: {SENTIMENT_MODEL}")
        self.tokenizer = AutoTokenizer.from_pretrained(SENTIMENT_MODEL)
        self.model = AutoModelForSequenceClassification.from_pretrained(SENTIMENT_MODEL)
        self.model.eval()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        logger.info(f"Sentiment model loaded on {self.device}")

    def score_texts(self, texts: List[str]) -> List[Tuple[float, float]]:
        """
        Score a list of texts.
        Returns list of (score, confidence) tuples.
          score:      -1.0 (negative) to +1.0 (positive)
          confidence: 0.0 to 1.0 (softmax probability of predicted label)
        """
        results = []

        for i in range(0, len(texts), SENTIMENT_BATCH_SIZE):
            batch = texts[i:i + SENTIMENT_BATCH_SIZE]
            inputs = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = torch.nn.functional.softmax(outputs.logits, dim=-1)

            # FinBERT labels: positive, negative, neutral
            id2label = self.model.config.id2label
            for j in range(len(batch)):
                prob_vector = probs[j].cpu().numpy()
                predicted_idx = prob_vector.argmax()
                label = id2label[predicted_idx]
                confidence = float(prob_vector[predicted_idx])
                score = LABEL_MAP.get(label, 0.0)

                # Weighted score: blend all three probabilities
                weighted_score = 0.0
                for idx, lbl in id2label.items():
                    weighted_score += LABEL_MAP.get(lbl, 0.0) * float(prob_vector[idx])

                results.append((weighted_score, confidence))

        return results

    def analyze_articles(self, articles: List[Article]) -> dict:
        """
        Analyze a batch of articles and return an aggregate daily score.

        Returns:
            {
                "score": float,           # -1.0 to +1.0
                "confidence": float,      # avg model confidence
                "article_count": int,
                "sample_headlines": list,  # top 3 most relevant
                "per_article": list,       # individual scores
            }
        """
        if not articles:
            return {
                "score": 0.0,
                "confidence": 0.0,
                "article_count": 0,
                "sample_headlines": [],
                "per_article": [],
            }

        # Combine title + summary for each article
        texts = [
            f"{a['title']}. {a['summary']}" if a["summary"] else a["title"]
            for a in articles
        ]

        scores = self.score_texts(texts)

        # Aggregate: confidence-weighted average
        total_weight = 0.0
        weighted_sum = 0.0
        per_article = []

        for article, (score, conf) in zip(articles, scores):
            weighted_sum += score * conf
            total_weight += conf
            per_article.append({
                "title": article["title"],
                "score": round(score, 4),
                "confidence": round(conf, 4),
                "url": article["url"],
            })

        avg_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        avg_confidence = total_weight / len(articles) if articles else 0.0

        # Pick top 3 most confident headlines for display
        sorted_articles = sorted(per_article, key=lambda x: abs(x["score"]) * x["confidence"], reverse=True)
        sample_headlines = [a["title"] for a in sorted_articles[:3]]

        return {
            "score": round(avg_score, 4),
            "confidence": round(avg_confidence, 4),
            "article_count": len(articles),
            "sample_headlines": sample_headlines,
            "per_article": per_article,
        }
