"""Unit tests for disaster entity extraction (T-030)."""

from __future__ import annotations

from app.ai.entity_extractor import (
    extract_entities,
    extract_location_phrase,
    extract_people_count,
    extract_resource_needed,
)


def test_extract_people_count_numeric():
    text = "Car crash with 5 passengers critically injured near flyover."
    assert extract_people_count(text) == 5

    text2 = "Family of 4 trapped on roof due to flood waters."
    assert extract_people_count(text2) == 4

    text3 = "Building collapsed, trapped: 7 under debris."
    assert extract_people_count(text3) == 7


def test_extract_people_count_hinglish():
    text = "Ghar me char log phanse hue hain aur ek buzug."
    assert extract_people_count(text) == 4

    text2 = "teen bache behosh pade hain."
    assert extract_people_count(text2) == 3


def test_extract_location_phrase():
    text = "Severe flooding at Sector 14 near metro station. Roads submerged."
    loc = extract_location_phrase(text)
    assert loc is not None
    assert "Sector 14" in loc

    text2 = "Water entered in Indira Nagar Colony near water tank."
    loc2 = extract_location_phrase(text2)
    assert loc2 is not None
    assert "Indira Nagar" in loc2


def test_extract_resource_needed():
    # Boat
    boat_text = "Water is 6 feet deep, need rescue boat to evacuate marooned residents."
    assert extract_resource_needed(boat_text) == "boat"

    # Ambulance
    amb_text = "Heart attack patient, unconscious with severe chest pain, send ambulance!"
    assert extract_resource_needed(amb_text) == "ambulance"

    # Rescue team
    rescue_text = (
        "Building collapsed, 4 people buried under heavy debris, need crane and rescue team."
    )
    assert extract_resource_needed(rescue_text) == "rescue_team"

    # Food kit
    food_text = "Relief camp running out of drinking water and dry food rations."
    assert extract_resource_needed(food_text) == "food_kit"


def test_extract_entities_full():
    text = "Head-on collision at Ring Road near flyover. 3 passengers bleeding heavily, ambulance needed urgently!"
    entities = extract_entities(text)
    assert entities.people_count == 3
    assert entities.location is not None
    assert "Ring Road" in entities.location
    assert entities.resource_needed == "ambulance"
