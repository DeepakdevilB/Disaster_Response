"""Text preprocessing pipeline for crisis reports (T-027).

Handles cleaning, emoji translation, Hinglish normalization, tokenization,
and dataset train/val/test splitting.
"""

from __future__ import annotations

import re
import unicodedata

# Common emergency emojis mapped to normalized tokens
EMOJI_MAP: dict[str, str] = {
    "🚨": " [emergency] ",
    "🔥": " [fire] ",
    "🌊": " [flood] ",
    "🏥": " [hospital] ",
    "⚠️": " [warning] ",
    "🆘": " [sos] ",
    "🚑": " [ambulance] ",
    "🚒": " [fire_truck] ",
    "⛵": " [boat] ",
    "⚡": " [electricity] ",
    "🌧️": " [rain] ",
    "🌧": " [rain] ",
    "💥": " [explosion] ",
    "🩸": " [bleeding] ",
}

# Hinglish numeral words mapped to numeric digits
HINGLISH_NUMERALS: dict[str, str] = {
    "ek": "1",
    "do": "2",
    "teen": "3",
    "tin": "3",
    "char": "4",
    "chaar": "4",
    "panch": "5",
    "paanch": "5",
    "che": "6",
    "chhe": "6",
    "sat": "7",
    "saat": "7",
    "ath": "8",
    "aath": "8",
    "nau": "9",
    "no": "9",
    "das": "10",
    "gyarah": "11",
    "barah": "12",
}

# Hinglish emergency terminology expansion/normalization
HINGLISH_KEYWORDS: dict[str, str] = {
    "bachao": "rescue help",
    "madad": "help",
    "jaldi": "urgently fast",
    "turant": "immediately urgent",
    "ghayal": "injured bleeding",
    "phanse": "trapped marooned",
    "phase": "trapped marooned",
    "fans": "trapped marooned",
    "fanse": "trapped marooned",
    "paani": "water flood",
    "pani": "water flood",
    "baadh": "flood",
    "badh": "flood",
    "aag": "fire blaze",
    "dhuan": "smoke toxic",
    "makaan": "building house",
    "chhat": "roof",
    "malba": "debris rubble collapse",
    "bhookamp": "earthquake collapse",
    "behosh": "unconscious critical",
    "khoon": "blood bleeding",
}


def normalize_emojis(text: str) -> str:
    """Translate emergency emojis to semantic text tokens and strip other emojis."""
    for emoji, token in EMOJI_MAP.items():
        text = text.replace(emoji, token)

    # Strip any remaining high-surrogate / pictorial characters
    cleaned_chars = []
    for ch in text:
        cat = unicodedata.category(ch)
        # Keep letters, numbers, punctuation, separators, symbols
        if cat in ("So", "Cs") and ord(ch) > 0x1F000:
            continue
        cleaned_chars.append(ch)
    return "".join(cleaned_chars)


def normalize_hinglish_terms(text: str) -> str:
    """Normalize Hinglish numerals and emergency keywords to standard semantic tokens."""
    tokens = text.split()
    normalized = []
    for token in tokens:
        clean_tok = re.sub(r"^[^\w]+|[^\w]+$", "", token.lower())
        if clean_tok in HINGLISH_NUMERALS:
            replaced = HINGLISH_NUMERALS[clean_tok]
            normalized.append(replaced)
        elif clean_tok in HINGLISH_KEYWORDS:
            replaced = HINGLISH_KEYWORDS[clean_tok]
            normalized.append(f"{clean_tok} {replaced}")
        else:
            normalized.append(token)
    return " ".join(normalized)


def clean_text(text: str) -> str:
    """Full preprocessing pipeline: Unicode normalization, emojis, Hinglish, whitespace."""
    if not text:
        return ""
    # Unicode canonical normalization
    text = unicodedata.normalize("NFKC", text)

    # Convert emergency emojis
    text = normalize_emojis(text)

    # Lowercase for consistent NLP processing
    text = text.lower()

    # Expand Hinglish numerals and terms
    text = normalize_hinglish_terms(text)

    # Replace URLs
    text = re.sub(r"https?://\S+|www\.\S+", " [url] ", text)

    # Replace phone numbers (10 digits)
    text = re.sub(r"\b\d{10}\b", " [phone] ", text)

    # Normalize punctuation and collapse excessive whitespace
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text: str) -> list[str]:
    """Tokenize preprocessed text into word tokens."""
    cleaned = clean_text(text)
    return [tok for tok in re.findall(r"\b\w+\b", cleaned) if tok]
