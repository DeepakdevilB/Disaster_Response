"""Entity extraction module for disaster reports (T-030).

Extracts structured information from crisis report text:
- people_count (affected / trapped persons)
- location (landmarks, addresses, geographic descriptors)
- resource_needed (ambulance, boat, rescue_team, medical_kit, food_kit)
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from app.ai.preprocessing import HINGLISH_NUMERALS


class ExtractedEntities(BaseModel):
    people_count: int = Field(
        default=0, ge=0, description="Estimated number of affected/trapped people"
    )
    location: str | None = Field(
        default=None, description="Extracted landmark, address, or location phrase"
    )
    resource_needed: str | None = Field(
        default=None,
        description="Recommended resource: ambulance, boat, rescue_team, medical_kit, food_kit",
    )
    raw_entities: dict[str, Any] = Field(default_factory=dict)


# Regex patterns for people count extraction
PEOPLE_COUNT_PATTERNS = [
    # "family of 4", "group of 5"
    re.compile(r"\b(?:family|group)\s+of\s+(\d+)\b", re.IGNORECASE),
    # "4 people", "12 passengers", "3 residents", "5 log", "2 bache"
    re.compile(
        r"\b(\d+)\s*(?:people|persons|passengers|victims|residents|workers|children|kids|patients|"
        r"members|citizens|log|bache|mahilayein|aadmi|vyakti|marooned|individuals)\b",
        re.IGNORECASE,
    ),
    # "trapped: 4", "injured: 2", "affected 6"
    re.compile(
        r"\b(?:trapped|buried|injured|affected|rescued|marooned)\s*(?:is|are|:|count)?\s*(\d+)\b",
        re.IGNORECASE,
    ),
    # "at least 5", "around 10"
    re.compile(r"\b(?:at least|around|nearly|approx)\s+(\d+)\b", re.IGNORECASE),
]

# Location extraction patterns
LOCATION_PATTERNS = [
    # "in Sector 14 near metro station", "at Main Market near SBI Bank"
    re.compile(
        r"\b(?:at|near|in|around|opposite|behind|beside)\s+([A-Z0-9][A-Za-z0-9\s,.-]+?(?:\b(?:colony|nagar|road|street|sector|chowk|ghat|bridge|flyover|station|hospital|market|area|block|lines|city|village|highway|marker)\b[A-Za-z0-9\s]*))",
        re.IGNORECASE,
    ),
    # Hinglish "Ganga Ghat Road ke paas", "Indira Nagar me"
    re.compile(
        r"([A-Z0-9][A-Za-z0-9\s,.-]+?)\s+(?:ke paas|ke samne|ke piche|me|par)\b",
        re.IGNORECASE,
    ),
]

# Resource indicators
RESOURCE_KEYWORDS: dict[str, list[str]] = {
    "boat": [
        "boat",
        "rescue boat",
        "dinghy",
        "raft",
        "ndrf boat",
        "flood",
        "submerged",
        "inundated",
        "marooned",
        "water level",
        "paani",
        "baadh",
        "chhat par",
    ],
    "ambulance": [
        "ambulance",
        "paramedic",
        "doctor",
        "stretcher",
        "bleeding",
        "heart attack",
        "cardiac",
        "stroke",
        "unconscious",
        "head trauma",
        "fracture",
        "labor",
        "maternity",
        "behosh",
        "khoon",
        "accident",
        "iv fluid",
    ],
    "rescue_team": [
        "rescue team",
        "fire brigade",
        "fire tender",
        "firefighters",
        "collapsed",
        "buried",
        "debris",
        "rubble",
        "malba",
        "lift stuck",
        "trapped inside",
        "earthmover",
        "crane",
        "toxic smoke",
        "chemical fire",
        "blaze",
        "aag",
    ],
    "medical_kit": [
        "medical kit",
        "first aid",
        "bandage",
        "medicines",
        "iv fluids",
        "antiseptic",
        "dehydration",
        "gastroenteritis",
        "vomiting",
        "asthma",
        "inhaler",
    ],
    "food_kit": [
        "food kit",
        "rations",
        "drinking water",
        "ration",
        "clean water",
        "relief shelter",
        "baby food",
        "milk powder",
        "dry food",
        "khana",
    ],
}


def extract_people_count(text: str) -> int:
    """Extract estimated number of people mentioned in text."""
    # First check standard numeric patterns
    for pat in PEOPLE_COUNT_PATTERNS:
        match = pat.search(text)
        if match:
            try:
                count = int(match.group(1))
                if 1 <= count <= 500:
                    return count
            except (ValueError, IndexError):
                continue

    # Second check Hinglish numeral words: "char log", "teen bache"
    lower = text.lower()
    for word, digit in HINGLISH_NUMERALS.items():
        pattern = rf"\b{word}\s*(?:log|bache|mahilayein|admi|aadmi|vyakti|members|people|persons)\b"
        if re.search(pattern, lower):
            return int(digit)

    return 0


def extract_location_phrase(text: str) -> str | None:
    """Extract prominent landmark, address, or location phrase."""
    for pat in LOCATION_PATTERNS:
        match = pat.search(text)
        if match:
            loc = match.group(1).strip()
            # Clean trailing punctuation and common words
            loc = re.sub(r"[,;:.!?]+$", "", loc).strip()
            generic_words = {"house", "building", "ground", "first floor", "water", "fire"}
            if 3 <= len(loc) <= 80 and loc.lower() not in generic_words:
                return loc

    return None


def extract_resource_needed(text: str) -> str | None:
    """Determine recommended primary resource from report content."""
    lower = text.lower()

    # Score each resource based on keyword matches
    scores: dict[str, int] = {}
    for resource, keywords in RESOURCE_KEYWORDS.items():
        score = sum(2 if f" {kw} " in f" {lower} " else 0 for kw in keywords)
        if score > 0:
            scores[resource] = score

    if not scores:
        return None

    # Return resource with highest matched keywords
    return max(scores, key=lambda k: scores[k])


def extract_entities(text: str) -> ExtractedEntities:
    """Extract all disaster entities from text."""
    if not text:
        return ExtractedEntities()

    people_count = extract_people_count(text)
    location = extract_location_phrase(text)
    resource = extract_resource_needed(text)

    return ExtractedEntities(
        people_count=people_count,
        location=location,
        resource_needed=resource,
        raw_entities={
            "people_count": people_count,
            "location": location,
            "resource_needed": resource,
        },
    )
