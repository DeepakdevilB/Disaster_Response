"""Unit tests for text preprocessing and Hinglish normalization (T-027)."""

from __future__ import annotations

from app.ai.preprocessing import (
    clean_text,
    normalize_emojis,
    normalize_hinglish_terms,
    tokenize,
)


def test_normalize_emojis():
    raw = "Urgent help needed 🔥 at building 🌊 water rising!"
    normalized = normalize_emojis(raw)
    assert "[fire]" in normalized
    assert "[flood]" in normalized


def test_normalize_hinglish_numerals():
    text = "Ghar me char log phanse hue hain aur do bache"
    normalized = normalize_hinglish_terms(text)
    assert "4" in normalized
    assert "2" in normalized


def test_normalize_hinglish_emergency_keywords():
    text = "Bachao jaldi turant paani bhar gaya hai"
    normalized = normalize_hinglish_terms(text)
    assert "rescue" in normalized
    assert "urgent" in normalized
    assert "water flood" in normalized


def test_clean_text_full_pipeline():
    raw = (
        "  🚨 HELP! Water 7 feet in Sector 14! 🌊 Call 9876543210 or visit https://disaster.org   "
    )
    cleaned = clean_text(raw)
    assert "[emergency]" in cleaned
    assert "[flood]" in cleaned
    assert "[phone]" in cleaned
    assert "[url]" in cleaned
    assert "sector 14" in cleaned
    # Ensure no excessive whitespace
    assert "  " not in cleaned


def test_tokenize():
    text = "Severe fire in warehouse, 3 people trapped"
    tokens = tokenize(text)
    assert "fire" in tokens
    assert "3" in tokens
    assert "trapped" in tokens
    assert len(tokens) >= 5
