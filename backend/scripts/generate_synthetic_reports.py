"""Synthetic crisis reports generator (T-026).

Produces realistic English and Hinglish emergency incident reports mapped to the platform's
taxonomy (medical, rescue, infrastructure, fire, flood, other) and severity levels
(LOW, MEDIUM, HIGH, CRITICAL) for training and evaluating NLP models.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "labeled" / "crisis_reports.csv"
)

# Core disaster categories
CATEGORIES = ["medical", "rescue", "infrastructure", "fire", "flood", "other"]
SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

LOCATIONS = [
    "Sector 14 near metro station",
    "Main Market near SBI Bank",
    "Ganga Ghat Road near bridge",
    "Indira Nagar Colony near water tank",
    "MG Road near junction",
    "Civil Lines near district hospital",
    "Railway Station Platform 2",
    "Shanti Nagar cross road",
    "Ring Road near flyover",
    "Kalyan Nagar 4th cross",
    "Yamuna river bank low lying area",
    "Subhash Chowk near clock tower",
    "Lal Baug industrial area",
    "Old City near historical gate",
    "National Highway 48 mile marker 42",
]

# Scenario templates per category with associated severity and resources
TEMPLATES = [
    # ---------------- FLOOD ----------------
    {
        "category": "flood",
        "severity": "CRITICAL",
        "resource": "boat",
        "min_people": 4,
        "max_people": 15,
        "templates": [
            "Water levels rose above 7 feet in {loc}. {n} people trapped on roof, water still rising fast! Send rescue boats immediately!",
            "Extreme flash flood at {loc}! {n} elderly citizens marooned inside house, flood water entered 1st floor. Urgent boat needed!",
            "{loc} me paani 8 foot chadh gaya hai! {n} log chhat par phanse hue hain, bachao please boat bhejo turant!",
            "Severe inundation at {loc}. Current is very strong, {n} persons clinging to trees. Need NDRF rescue boat right now!",
            "{loc} ke paas baadh ka paani bohot tez hai, {n} bache aur mahilayein phansi hain, jaldi rescue team bhejo!",
        ],
    },
    {
        "category": "flood",
        "severity": "HIGH",
        "resource": "boat",
        "min_people": 2,
        "max_people": 6,
        "templates": [
            "Heavy waterlogging at {loc}, water is knee-deep and entering ground floors. {n} residents unable to evacuate.",
            "{loc} me 4 feet paani bhar gaya hai. {n} log ghar se nikal nahi pa rahe hain. Need evacuation assistance.",
            "River overflowed near {loc}. Roads are submerged and power is cut off. {n} people need safe shelter.",
            "{loc} area is completely inundated, cars floating and {n} people stuck inside apartment lobby.",
        ],
    },
    {
        "category": "flood",
        "severity": "MEDIUM",
        "resource": "food_kit",
        "min_people": 1,
        "max_people": 4,
        "templates": [
            "Water stagnation of 2 feet near {loc}. Drainage blocked, drinking water contaminated. Need clean food and water kits.",
            "{loc} me paani bharne se rashan aur drinking water khatam ho gaya hai. {n} families need food kits.",
            "Moderate street flooding near {loc}. Traffic blocked and shops waterlogged.",
        ],
    },
    {
        "category": "flood",
        "severity": "LOW",
        "resource": "none",
        "min_people": 0,
        "max_people": 0,
        "templates": [
            "Minor waterlogging on the side of {loc}. Vehicles moving slowly, municipal drain cleaning needed.",
            "{loc} par halka paani jama hai sadak kinare, koi fasna nahi hua hai.",
            "Water accumulation near {loc} bus stand after morning rains. Potholes covered.",
        ],
    },
    # ---------------- FIRE ----------------
    {
        "category": "fire",
        "severity": "CRITICAL",
        "resource": "rescue_team",
        "min_people": 3,
        "max_people": 12,
        "templates": [
            "Massive chemical fire broken out at {loc}! {n} workers trapped inside warehouse with toxic smoke! Fire tender and rescue team needed!",
            "Gas cylinder explosion inside 3-story building at {loc}. Heavy blaze spreading, {n} people crying for help on upper floor!",
            "{loc} me bishaan aag lag gayi hai factory me! {n} log andar fas gaye hain, dhuan bohot tez hai. Turant fire brigade aur rescue team bhejo!",
            "Commercial complex caught fire near {loc}. Exit stairs blocked by flames, {n} shoppers trapped on 2nd floor!",
        ],
    },
    {
        "category": "fire",
        "severity": "HIGH",
        "resource": "rescue_team",
        "min_people": 1,
        "max_people": 4,
        "templates": [
            "House fire at {loc}. Kitchen caught fire from LPG leak, {n} persons suffered minor burns and need rescue.",
            "{loc} me dukan me aag lag gayi hai. Flames reaching adjacent buildings, {n} people evacuated.",
            "Electrical transformer exploded and caught fire near {loc}. Sparks spreading to nearby trees and houses.",
        ],
    },
    {
        "category": "fire",
        "severity": "MEDIUM",
        "resource": "none",
        "min_people": 0,
        "max_people": 2,
        "templates": [
            "Garbage dump fire spreading smoke near {loc}. Residents facing breathing trouble.",
            "{loc} ke paas dry grass caught fire in empty plot. No structural damage yet.",
            "Smoke coming out of abandoned godown near {loc}. Fire brigade should inspect.",
        ],
    },
    {
        "category": "fire",
        "severity": "LOW",
        "resource": "none",
        "min_people": 0,
        "max_people": 0,
        "templates": [
            "Controlled trash burning near {loc} causing smoke nuisance on the road.",
            "Small waste bin fire near {loc} footpath, local shopkeepers putting it out with sand.",
        ],
    },
    # ---------------- MEDICAL ----------------
    {
        "category": "medical",
        "severity": "CRITICAL",
        "resource": "ambulance",
        "min_people": 1,
        "max_people": 5,
        "templates": [
            "Head-on collision between bus and truck at {loc}. {n} passengers critically injured with severe bleeding and head trauma! Need multiple ambulances urgently!",
            "Heart attack and unconscious elderly patient at {loc}. Oxygen level dropping rapidly, pulse weak. Send advanced life support ambulance immediately!",
            "{loc} par bura accident hua hai! {n} log behosh pade hain, bohot khoon beh raha hai. Jaldi ambulance bhejo please!",
            "Electrocution accident at {loc}. High voltage wire snapped, {n} victims unconscious with severe electrical burns!",
        ],
    },
    {
        "category": "medical",
        "severity": "HIGH",
        "resource": "ambulance",
        "min_people": 1,
        "max_people": 3,
        "templates": [
            "Pregnant woman in labor with severe complications at {loc}. Ambulance needed to shift to maternity hospital.",
            "Fall from height at construction site in {loc}. {n} workers with multiple bone fractures.",
            "{loc} me ek buzug gir gaye hain, sar pe chot aayi hai aur behoshi hai. Ambulance required.",
            "Diabetic ketoacidosis patient unresponsive at {loc}. Doctor advised immediate emergency transfer.",
        ],
    },
    {
        "category": "medical",
        "severity": "MEDIUM",
        "resource": "medical_kit",
        "min_people": 1,
        "max_people": 3,
        "templates": [
            "Severe gastroenteritis and dehydration outbreak at {loc}. {n} children throwing up, need IV fluids and medical kits.",
            "{loc} me food poisoning ke shikar {n} log hain. Vomiting and cramps, medical aid needed.",
            "Asthma attack patient struggling for breath near {loc}, inhaler exhausted.",
        ],
    },
    {
        "category": "medical",
        "severity": "LOW",
        "resource": "medical_kit",
        "min_people": 1,
        "max_people": 1,
        "templates": [
            "Person suffered minor knee scrape from bicycle skid at {loc}. First aid bandage applied.",
            "Mild fever and body pain report near {loc}. Routine checkup required.",
        ],
    },
    # ---------------- RESCUE ----------------
    {
        "category": "rescue",
        "severity": "CRITICAL",
        "resource": "rescue_team",
        "min_people": 2,
        "max_people": 10,
        "templates": [
            "Old 4-storey residential building collapsed at {loc}! At least {n} people buried under concrete debris and shouting for help! Heavy rescue equipment needed urgently!",
            "Landslide swept mud onto houses at {loc}! {n} villagers trapped under mud and rubble! Send NDRF search and rescue team with earthmovers!",
            "{loc} me purana makaan gir gaya hai! Malbe me {n} log dabe hue hain, niche se aawazein aa rahi hain. Jaldi rescue team bhejo!",
            "Well caved in during cleaning at {loc}. {n} laborers trapped 40 feet underground with scarce oxygen!",
        ],
    },
    {
        "category": "rescue",
        "severity": "HIGH",
        "resource": "rescue_team",
        "min_people": 1,
        "max_people": 4,
        "templates": [
            "Elevator stalled between 7th and 8th floor at {loc}. {n} people stuck inside for 2 hours with fan off.",
            "Car fell into deep drainage canal near {loc}. {n} passengers trapped inside cabin with rising water.",
            "{loc} me lift kharab ho gayi hai, {n} log fas gaye hain ghutan ho rahi hai.",
        ],
    },
    {
        "category": "rescue",
        "severity": "MEDIUM",
        "resource": "rescue_team",
        "min_people": 1,
        "max_people": 2,
        "templates": [
            "Stray dog and child stuck in dry storm drain opening at {loc}. Firefighters needed with ladder.",
            "Large branch fell trapping a small vehicle at {loc}. No serious injury, need rescue saw to clear.",
        ],
    },
    {
        "category": "rescue",
        "severity": "LOW",
        "resource": "none",
        "min_people": 0,
        "max_people": 1,
        "templates": [
            "Cat stuck on high electrical pole near {loc}. Locals requesting municipal assistance.",
            "Door lock jammed in ground floor room at {loc}, carpenter or lock technician needed.",
        ],
    },
    # ---------------- INFRASTRUCTURE ----------------
    {
        "category": "infrastructure",
        "severity": "CRITICAL",
        "resource": "rescue_team",
        "min_people": 0,
        "max_people": 0,
        "templates": [
            "Main highway bridge over river developed large cracks and foundation shift at {loc}! Immediate traffic closure and structural inspection before collapse!",
            "High-tension 11kV electrical wire snapped and fell across flooded road at {loc}! Severe public electrocution hazard, cut power grid immediately!",
            "{loc} par bridge tutne ki aashanka hai, pillar crack ho gaya hai, rasta turant band karo!",
        ],
    },
    {
        "category": "infrastructure",
        "severity": "HIGH",
        "resource": "none",
        "min_people": 0,
        "max_people": 0,
        "templates": [
            "Massive sinkhole opened on main road at {loc}. Crater is 15 feet wide and 10 feet deep, traffic completely halted.",
            "Main municipal water pipeline burst at {loc}, flooding road and cutting drinking water to 5000 households.",
            "{loc} me sadak dhas gayi hai bohot bada gaddha ban gaya hai.",
        ],
    },
    {
        "category": "infrastructure",
        "severity": "MEDIUM",
        "resource": "none",
        "min_people": 0,
        "max_people": 0,
        "templates": [
            "Traffic signals out of order at {loc} intersection for past 6 hours causing gridlock.",
            "Fallen tree blocking two lanes of road at {loc}. Municipal crane needed to clear.",
            "Streetlights not functioning in entire sector near {loc}, complete dark stretch.",
        ],
    },
    {
        "category": "infrastructure",
        "severity": "LOW",
        "resource": "none",
        "min_people": 0,
        "max_people": 0,
        "templates": [
            "Open manhole cover missing on footpath near {loc}. Pedestrian tripping hazard.",
            "Pothole on service lane near {loc} causing slow vehicular movement.",
            "{loc} ke paas footpath par manhole ka dhakkan toota hua hai.",
        ],
    },
    # ---------------- OTHER ----------------
    {
        "category": "other",
        "severity": "HIGH",
        "resource": "rescue_team",
        "min_people": 1,
        "max_people": 1,
        "templates": [
            "Lost 6-year-old child wearing red shirt missing in large crowd near {loc}. Parents searching panicking.",
            "{loc} mela ground me ek bacha kho gaya hai, announcements needed.",
        ],
    },
    {
        "category": "other",
        "severity": "MEDIUM",
        "resource": "food_kit",
        "min_people": 0,
        "max_people": 0,
        "templates": [
            "Relief shelter near {loc} running out of dry food rations and baby milk powder.",
            "Water supply tanker needed at community hall near {loc}.",
        ],
    },
    {
        "category": "other",
        "severity": "LOW",
        "resource": "none",
        "min_people": 0,
        "max_people": 0,
        "templates": [
            "General inquiry regarding disaster relief helpline numbers for {loc} district.",
            "Volunteers asking where to deposit clothes donation near {loc}.",
            "{loc} relief camp timing inquiry from citizen.",
        ],
    },
]


def generate_reports(count: int = 350, seed: int = 42) -> list[dict[str, str | int]]:
    random.seed(seed)
    records = []

    for _ in range(count):
        spec = random.choice(TEMPLATES)
        loc = random.choice(LOCATIONS)
        if spec["min_people"] == spec["max_people"]:
            n_people = spec["min_people"]
        else:
            n_people = random.randint(spec["min_people"], spec["max_people"])

        template = random.choice(spec["templates"])
        text = template.format(loc=loc, n=n_people)

        # Detect language
        is_hinglish = any(
            w in text.lower()
            for w in [
                "me",
                "hai",
                "ka",
                "ki",
                "ke",
                "log",
                "bohot",
                "jaldi",
                "fas",
                "bhejo",
                "aag",
                "paani",
            ]
        )
        lang = "hi-Latn" if is_hinglish else "en"

        records.append(
            {
                "text": text,
                "category": spec["category"],
                "severity": spec["severity"],
                "people_count": n_people,
                "location": loc,
                "resource_needed": spec["resource"],
                "language": lang,
            }
        )

    return records


def save_dataset(records: list[dict[str, str | int]], path: Path = OUTPUT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "text",
        "category",
        "severity",
        "people_count",
        "location",
        "resource_needed",
        "language",
    ]
    with open(path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


if __name__ == "__main__":
    data = generate_reports(count=400)
    save_dataset(data)
    print(f"Generated {len(data)} labeled records -> {OUTPUT_PATH}")
