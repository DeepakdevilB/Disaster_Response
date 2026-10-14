"""Disaster severity classifier with text and engineered feature fusion (T-029).

Predicts severity: LOW | MEDIUM | HIGH | CRITICAL with probability distribution.
Prioritizes high recall on CRITICAL incidents to prevent under-triaging emergencies.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from app.ai.entity_extractor import extract_entities
from app.ai.preprocessing import clean_text

logger = logging.getLogger(__name__)

SEVERITY_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

CRITICAL_TERMS = {
    "unconscious",
    "head-on",
    "explosion",
    "severe bleeding",
    "buried",
    "collapsed",
    "toxic smoke",
    "chemical fire",
    "behosh",
    "bishaan",
    "snapped wire",
    "cardiac arrest",
    "electrocution",
    "flash flood",
    "marooned",
    "chhat par",
    "critical",
}
HIGH_TERMS = {
    "trapped",
    "fracture",
    "labor",
    "maternity",
    "inundated",
    "submerged",
    "knee-deep",
    "sinkhole",
    "water burst",
    "blaze",
    "aag",
    "stuck",
}
MEDIUM_TERMS = {
    "contaminated",
    "food poisoning",
    "vomiting",
    "stagnation",
    "smoke nuisance",
    "traffic gridlock",
    "fallen tree",
    "asthma",
    "ration",
    "gastroenteritis",
}


def compute_engineered_features(text: str, people_count: int | None = None) -> np.ndarray:
    """Compute dense engineered feature vector: log_people, crit_count, high_count, flags."""
    if people_count is None:
        entities = extract_entities(text)
        people_count = entities.people_count

    lower = text.lower()
    log_people = math.log1p(float(people_count))

    crit_matches = sum(1 for term in CRITICAL_TERMS if term in lower)
    high_matches = sum(1 for term in HIGH_TERMS if term in lower)

    medical_flag = (
        1.0
        if any(
            t in lower
            for t in ["bleeding", "unconscious", "cardiac", "stroke", "accident", "behosh"]
        )
        else 0.0
    )
    trapped_flag = (
        1.0
        if any(
            t in lower for t in ["trapped", "buried", "stranded", "marooned", "malba", "lift stuck"]
        )
        else 0.0
    )

    return np.array(
        [[log_people, float(crit_matches), float(high_matches), medical_flag, trapped_flag]],
        dtype=float,
    )


class SeverityClassifier:
    """Hybrid ML + Engineered Feature severity triage model."""

    def __init__(
        self,
        vectorizer: TfidfVectorizer | None = None,
        clf: LogisticRegression | None = None,
    ) -> None:
        self.model_name = "severity_hybrid_logreg"
        self.model_version = "v1.0.0"
        self.vectorizer = vectorizer
        self.clf = clf

    @classmethod
    def train(
        cls,
        texts: list[str],
        severities: list[str],
        people_counts: list[int] | None = None,
    ) -> SeverityClassifier:
        """Train TF-IDF + engineered feature classifier."""
        cleaned_texts = [clean_text(t) for t in texts]

        # 1. Text TF-IDF
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, max_features=3000)
        x_text = vectorizer.fit_transform(cleaned_texts)

        # 2. Engineered feature matrix
        feat_rows = []
        for i, text in enumerate(texts):
            p_count = people_counts[i] if people_counts is not None else None
            feat_rows.append(compute_engineered_features(text, p_count)[0])
        x_dense = np.array(feat_rows)

        # 3. Fuse sparse text + dense engineered features
        x_all = hstack([x_text, x_dense])

        # 4. Train classifier with higher weight on CRITICAL to minimize false negatives
        clf = LogisticRegression(
            max_iter=1000,
            class_weight={"LOW": 1.0, "MEDIUM": 1.2, "HIGH": 1.5, "CRITICAL": 2.2},
            random_state=42,
        )
        clf.fit(x_all, severities)

        instance = cls(vectorizer=vectorizer, clf=clf)
        logger.info("SeverityClassifier trained successfully on %d records", len(texts))
        return instance

    def predict(
        self,
        text: str,
        people_count: int | None = None,
    ) -> tuple[str, float, dict[str, float]]:
        """Predict severity with confidence and probability distribution."""
        cleaned = clean_text(text)
        if not cleaned:
            return "LOW", 0.5, {"LOW": 0.5, "MEDIUM": 0.25, "HIGH": 0.15, "CRITICAL": 0.1}

        # 1. ML inference if model is fitted
        if self.vectorizer is not None and self.clf is not None:
            try:
                x_text = self.vectorizer.transform([cleaned])
                x_dense = compute_engineered_features(text, people_count)
                x_all = hstack([x_text, x_dense])

                classes = list(self.clf.classes_)
                probas = self.clf.predict_proba(x_all)[0]
                proba_dict = {str(c): float(p) for c, p in zip(classes, probas, strict=False)}

                # Fill any missing
                for s in SEVERITY_LEVELS:
                    if s not in proba_dict:
                        proba_dict[s] = 0.0

                top_sev = max(proba_dict, key=lambda k: proba_dict[k])
                top_conf = proba_dict[top_sev]

                # Triage Safety Override: If people are trapped/buried or life-threat terms exist,
                # ensure severity is at least HIGH or CRITICAL.
                top_sev, top_conf, proba_dict = self._apply_safety_guardrails(
                    text, people_count or 0, top_sev, top_conf, proba_dict
                )

                return top_sev, round(top_conf, 4), {k: round(v, 4) for k, v in proba_dict.items()}
            except Exception as exc:
                logger.warning("ML severity prediction failed, using fallback: %s", exc)

        # 2. Rule-based triage fallback
        return self._heuristic_predict(text, people_count or 0)

    def _apply_safety_guardrails(
        self,
        text: str,
        people_count: int,
        top_sev: str,
        top_conf: float,
        probas: dict[str, float],
    ) -> tuple[str, float, dict[str, float]]:
        """Ensure severe emergencies cannot be mistakenly triaged as LOW/MEDIUM."""
        lower = text.lower()
        has_crit = any(term in lower for term in CRITICAL_TERMS)
        has_high = any(term in lower for term in HIGH_TERMS)

        if has_crit or (people_count >= 5 and has_high):
            if top_sev in ("LOW", "MEDIUM"):
                top_sev = "CRITICAL"
                top_conf = max(top_conf, 0.88)
                probas["CRITICAL"] = top_conf
                probas["LOW"] = min(probas["LOW"], 0.05)
        elif (has_high or people_count >= 3) and top_sev == "LOW":
            top_sev = "HIGH"
            top_conf = max(top_conf, 0.75)
            probas["HIGH"] = top_conf
            probas["LOW"] = 0.05

        return top_sev, top_conf, probas

    def _heuristic_predict(
        self,
        text: str,
        people_count: int,
    ) -> tuple[str, float, dict[str, float]]:
        """Explainable heuristic scoring based on disaster indicators."""
        lower = text.lower()
        crit_score = sum(3 for t in CRITICAL_TERMS if t in lower)
        high_score = sum(2 for t in HIGH_TERMS if t in lower)
        med_score = sum(1 for t in MEDIUM_TERMS if t in lower)

        if people_count >= 5:
            crit_score += 4
        elif people_count >= 2:
            high_score += 2

        if crit_score >= 3:
            return "CRITICAL", 0.90, {"LOW": 0.02, "MEDIUM": 0.08, "HIGH": 0.20, "CRITICAL": 0.70}
        if high_score >= 2 or (crit_score > 0):
            return "HIGH", 0.80, {"LOW": 0.05, "MEDIUM": 0.20, "HIGH": 0.65, "CRITICAL": 0.10}
        if med_score >= 1 or people_count >= 1:
            return "MEDIUM", 0.70, {"LOW": 0.15, "MEDIUM": 0.65, "HIGH": 0.15, "CRITICAL": 0.05}
        return "LOW", 0.65, {"LOW": 0.65, "MEDIUM": 0.20, "HIGH": 0.10, "CRITICAL": 0.05}

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "classes": SEVERITY_LEVELS,
        }
