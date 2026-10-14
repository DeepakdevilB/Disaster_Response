"""Model training script for Category and Severity classifiers (T-028, T-029).

Loads labeled crisis data, trains models, and saves artifacts to backend/models/.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import joblib

from app.ai.category_classifier import CategoryClassifier
from app.ai.registry import get_models_dir
from app.ai.severity_classifier import SeverityClassifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATASET_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "labeled" / "crisis_reports.csv"
)


def train_and_persist_all() -> None:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found at {DATASET_PATH}. Run generate_synthetic_reports.py first."
        )

    texts, categories, severities, counts = [], [], [], []
    with open(DATASET_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            texts.append(row["text"])
            categories.append(row["category"])
            severities.append(row["severity"])
            counts.append(int(row["people_count"]) if row["people_count"] else 0)

    logger.info("Loaded %d training samples from %s", len(texts), DATASET_PATH)

    # 1. Train Category Classifier
    cat_model = CategoryClassifier.train(texts, categories)
    cat_path = get_models_dir() / "category_model.joblib"
    joblib.dump(cat_model, cat_path)
    logger.info("Persisted CategoryClassifier -> %s", cat_path)

    # 2. Train Severity Classifier
    sev_model = SeverityClassifier.train(texts, severities, counts)
    sev_path = get_models_dir() / "severity_model.joblib"
    joblib.dump(sev_model, sev_path)
    logger.info("Persisted SeverityClassifier -> %s", sev_path)

    print("\nTraining completed successfully:")
    print(f" - Category model: {cat_path}")
    print(f" - Severity model: {sev_path}")


if __name__ == "__main__":
    train_and_persist_all()
