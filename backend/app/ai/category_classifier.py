"""Incident category classification model (T-028).

Classifies crisis report text into taxonomy:
medical | rescue | infrastructure | fire | flood | other
"""

from __future__ import annotations

import logging
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from app.ai.preprocessing import clean_text

logger = logging.getLogger(__name__)

CATEGORIES = ["medical", "rescue", "infrastructure", "fire", "flood", "other"]

# Strong heuristic keywords for fallback or boosting
KEYWORD_HEURISTICS: dict[str, list[str]] = {
    "flood": [
        "flood",
        "water",
        "submerged",
        "inundated",
        "paani",
        "baadh",
        "dam",
        "river",
        "overflow",
    ],
    "fire": ["fire", "blaze", "smoke", "cylinder", "flames", "burn", "aag", "dhuan", "explosion"],
    "medical": [
        "bleeding",
        "cardiac",
        "heart attack",
        "injured",
        "unconscious",
        "ambulance",
        "hospital",
        "fracture",
        "labor",
        "maternity",
        "vomiting",
        "asthma",
        "behosh",
        "khoon",
    ],
    "rescue": [
        "collapsed",
        "trapped",
        "debris",
        "rubble",
        "buried",
        "malba",
        "lift stuck",
        "landslide",
        "caved in",
        "phanso",
        "bachao",
    ],
    "infrastructure": [
        "bridge",
        "flyover",
        "pipeline",
        "power line",
        "wire",
        "sinkhole",
        "road crack",
        "manhole",
        "traffic light",
        "blackout",
        "substation",
    ],
    "other": [
        "lost child",
        "relief camp",
        "inquiry",
        "volunteer",
        "rations",
        "camp",
        "clothes donation",
    ],
}


class CategoryClassifier:
    """TF-IDF + LogisticRegression category classifier with fallback heuristics."""

    def __init__(self, pipeline: Pipeline | None = None) -> None:
        self.model_name = "category_tfidf_logreg"
        self.model_version = "v1.0.0"
        self.pipeline: Pipeline | None = pipeline

    @classmethod
    def train(cls, texts: list[str], labels: list[str]) -> CategoryClassifier:
        """Train TF-IDF + Logistic Regression pipeline on labeled crisis text."""
        cleaned_texts = [clean_text(t) for t in texts]
        pipeline = Pipeline(
            [
                (
                    "tfidf",
                    TfidfVectorizer(
                        ngram_range=(1, 2),
                        sublinear_tf=True,
                        max_features=5000,
                    ),
                ),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=1000,
                        class_weight="balanced",
                        random_state=42,
                    ),
                ),
            ]
        )
        pipeline.fit(cleaned_texts, labels)
        instance = cls(pipeline=pipeline)
        logger.info("CategoryClassifier trained successfully on %d records", len(texts))
        return instance

    def predict(self, text: str) -> tuple[str, float, dict[str, float]]:
        """Predict disaster category with confidence and class distribution."""
        cleaned = clean_text(text)
        if not cleaned:
            return "other", 0.5, {c: (1.0 / len(CATEGORIES)) for c in CATEGORIES}

        # 1. If ML pipeline is trained and available, run inference
        if self.pipeline is not None:
            try:
                classes = list(self.pipeline.classes_)
                probas = self.pipeline.predict_proba([cleaned])[0]
                proba_dict = {str(c): float(p) for c, p in zip(classes, probas, strict=False)}

                # Fill any missing categories with 0.0
                for cat in CATEGORIES:
                    if cat not in proba_dict:
                        proba_dict[cat] = 0.0

                top_cat = max(proba_dict, key=lambda k: proba_dict[k])
                top_conf = proba_dict[top_cat]

                # High-confidence model prediction
                if top_conf >= 0.40:
                    return (
                        top_cat,
                        round(top_conf, 4),
                        {k: round(v, 4) for k, v in proba_dict.items()},
                    )
            except Exception as exc:
                logger.warning("ML inference failed, falling back to heuristics: %s", exc)

        # 2. Heuristic fallback / hybrid match
        return self._heuristic_predict(cleaned)

    def _heuristic_predict(self, text: str) -> tuple[str, float, dict[str, float]]:
        """Explainable keyword scoring when ML is below confidence threshold or uninitialized."""
        scores: dict[str, int] = {cat: 0 for cat in CATEGORIES}
        words = set(text.lower().split())

        for cat, keywords in KEYWORD_HEURISTICS.items():
            for kw in keywords:
                if kw in words or f" {kw} " in f" {text.lower()} ":
                    scores[cat] += 2

        total_score = sum(scores.values())
        if total_score == 0:
            default_prob = round(1.0 / len(CATEGORIES), 4)
            return "other", 0.5, {c: default_prob for c in CATEGORIES}

        # Softmax / normalized distribution
        proba_dict = {cat: round(score / total_score, 4) for cat, score in scores.items()}
        top_cat = max(proba_dict, key=lambda k: proba_dict[k])
        confidence = min(0.95, max(0.60, proba_dict[top_cat]))
        return top_cat, round(confidence, 4), proba_dict

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "classes": CATEGORIES,
        }
