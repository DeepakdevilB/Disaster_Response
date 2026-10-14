"""Unit tests for situation summarizer (T-034)."""

from __future__ import annotations

from app.ai.summarizer import generate_deterministic_summary, summarize_cluster


def test_deterministic_summary_flood_cluster():
    reports = [
        {
            "category": "flood",
            "severity": "CRITICAL",
            "raw_text": "Water levels reached 7 feet, 5 people marooned on roof",
            "location_text": "Sector 14 near metro",
            "people_count": 5,
        },
        {
            "category": "flood",
            "severity": "HIGH",
            "raw_text": "Flooding entering ground floors, electricity cut",
            "location_text": "Sector 14 near metro",
            "people_count": 3,
        },
    ]

    summary = generate_deterministic_summary(reports)
    assert summary.total_reports == 2
    assert summary.primary_category == "flood"
    assert summary.severity == "CRITICAL"
    assert summary.estimated_people_affected == 8
    assert "Sector 14" in summary.summary
    assert len(summary.key_risks) >= 1
    assert any("boat" in act.lower() for act in summary.recommended_actions)
    assert summary.is_fallback is True


def test_summarize_cluster_fallback_on_offline_ollama():
    # If Ollama is not running on localhost, summarize_cluster must gracefully return deterministic summary without error
    reports = [
        {
            "category": "fire",
            "severity": "CRITICAL",
            "raw_text": "Factory fire with chemical fumes spreading",
            "location_text": "Lal Baug industrial area",
            "people_count": 4,
        }
    ]

    result = summarize_cluster(reports, ollama_url="http://127.0.0.1:59999/api/generate")
    assert result.total_reports == 1
    assert result.primary_category == "fire"
    assert "Lal Baug" in result.summary
    assert len(result.key_risks) >= 1
