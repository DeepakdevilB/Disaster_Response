"""Unit tests for Category and Severity classifiers and registry pipeline (T-028, T-029, T-032)."""

from __future__ import annotations

from app.ai.category_classifier import CategoryClassifier
from app.ai.registry import run_ai_pipeline
from app.ai.severity_classifier import SeverityClassifier


def test_category_classifier_heuristics():
    clf = CategoryClassifier()
    cat, conf, probas = clf.predict("Heavy flood water entered ground floor houses, submerged cars")
    assert cat == "flood"
    assert conf >= 0.50
    assert "flood" in probas

    cat_fire, conf_fire, _ = clf.predict(
        "Gas cylinder blast caught building on fire, heavy blaze and smoke"
    )
    assert cat_fire == "fire"
    assert conf_fire >= 0.50

    cat_med, _, _ = clf.predict(
        "Cardiac arrest victim unconscious with severe bleeding, need ambulance"
    )
    assert cat_med == "medical"


def test_severity_classifier_safety_guardrails():
    clf = SeverityClassifier()
    # Life-threatening phrases must never be triaged as LOW
    sev, conf, probas = clf.predict(
        "Chemical warehouse explosion, toxic smoke, 6 people trapped and unconscious",
        people_count=6,
    )
    assert sev == "CRITICAL"
    assert conf >= 0.80
    assert probas["CRITICAL"] > probas["LOW"]


def test_run_ai_pipeline_end_to_end():
    text = "Head-on collision at Ring Road near flyover. 4 people unconscious with severe bleeding. Need ambulance immediately!"
    result = run_ai_pipeline(text)

    assert "model_name" in result
    assert "model_version" in result
    assert result["predicted_category"] == "medical"
    assert result["predicted_severity"] in ("HIGH", "CRITICAL")
    assert result["category_confidence"] > 0.4
    assert result["severity_confidence"] > 0.4
    assert result["extracted_entities"]["people_count"] == 4
    assert result["extracted_entities"]["resource_needed"] == "ambulance"
    assert "category_probabilities" in result["raw_output"]
