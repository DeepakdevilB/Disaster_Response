"""AI Model Registry and Inference Pipeline (T-032).

Loads and caches category and severity models, handles versioning and persistence,
and executes the unified AI triage pipeline.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

import joblib

from app.ai.category_classifier import CategoryClassifier
from app.ai.entity_extractor import ExtractedEntities, extract_entities
from app.ai.severity_classifier import SeverityClassifier

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"
DATASET_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "labeled" / "crisis_reports.csv"
)

_CATEGORY_MODEL: CategoryClassifier | None = None
_SEVERITY_MODEL: SeverityClassifier | None = None


def get_models_dir() -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return MODELS_DIR


def load_or_train_category_model() -> CategoryClassifier:
    """Load cached category classifier from disk, or train from labeled CSV."""
    global _CATEGORY_MODEL
    if _CATEGORY_MODEL is not None:
        return _CATEGORY_MODEL

    artifact_path = get_models_dir() / "category_model.joblib"
    if artifact_path.exists():
        try:
            _CATEGORY_MODEL = joblib.load(artifact_path)
            logger.info("Loaded CategoryClassifier from %s", artifact_path)
            return _CATEGORY_MODEL
        except Exception as exc:
            logger.warning("Failed to load category artifact, training fresh: %s", exc)

    # Train from dataset if available
    if DATASET_PATH.exists():
        texts, labels = [], []
        with open(DATASET_PATH, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                texts.append(row["text"])
                labels.append(row["category"])
        _CATEGORY_MODEL = CategoryClassifier.train(texts, labels)
        try:
            joblib.dump(_CATEGORY_MODEL, artifact_path)
            logger.info("Saved trained CategoryClassifier to %s", artifact_path)
        except Exception as exc:
            logger.warning("Could not persist category model artifact: %s", exc)
        return _CATEGORY_MODEL

    # Fallback to empty model (rule heuristics)
    _CATEGORY_MODEL = CategoryClassifier()
    return _CATEGORY_MODEL


def load_or_train_severity_model() -> SeverityClassifier:
    """Load cached severity classifier from disk, or train from labeled CSV."""
    global _SEVERITY_MODEL
    if _SEVERITY_MODEL is not None:
        return _SEVERITY_MODEL

    artifact_path = get_models_dir() / "severity_model.joblib"
    if artifact_path.exists():
        try:
            _SEVERITY_MODEL = joblib.load(artifact_path)
            logger.info("Loaded SeverityClassifier from %s", artifact_path)
            return _SEVERITY_MODEL
        except Exception as exc:
            logger.warning("Failed to load severity artifact, training fresh: %s", exc)

    if DATASET_PATH.exists():
        texts, sevs, counts = [], [], []
        with open(DATASET_PATH, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                texts.append(row["text"])
                sevs.append(row["severity"])
                counts.append(int(row["people_count"]) if row["people_count"] else 0)
        _SEVERITY_MODEL = SeverityClassifier.train(texts, sevs, counts)
        try:
            joblib.dump(_SEVERITY_MODEL, artifact_path)
            logger.info("Saved trained SeverityClassifier to %s", artifact_path)
        except Exception as exc:
            logger.warning("Could not persist severity model artifact: %s", exc)
        return _SEVERITY_MODEL

    _SEVERITY_MODEL = SeverityClassifier()
    return _SEVERITY_MODEL


def run_ai_pipeline(text: str) -> dict[str, Any]:
    """Execute complete AI NLP pipeline:

    1. Entity extraction (people count, location, resources)
    2. Category classification with confidence
    3. Severity classification with confidence & safety floor
    """
    entities: ExtractedEntities = extract_entities(text)
    cat_model = load_or_train_category_model()
    sev_model = load_or_train_severity_model()

    pred_cat, cat_conf, cat_probas = cat_model.predict(text)
    pred_sev, sev_conf, sev_probas = sev_model.predict(text, entities.people_count)

    return {
        "model_name": f"{cat_model.model_name}+{sev_model.model_name}",
        "model_version": f"{cat_model.model_version}/{sev_model.model_version}",
        "predicted_category": pred_cat,
        "category_confidence": cat_conf,
        "predicted_severity": pred_sev,
        "severity_confidence": sev_conf,
        "extracted_entities": entities.model_dump(),
        "raw_output": {
            "category_probabilities": cat_probas,
            "severity_probabilities": sev_probas,
            "people_count": entities.people_count,
            "location": entities.location,
            "resource_needed": entities.resource_needed,
        },
    }
