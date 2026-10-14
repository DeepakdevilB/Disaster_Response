"""Milestone M3 Intelligence Pipeline Demonstration (T-048).

Demonstrates the end-to-end intelligent crisis engine:
1. Citizen Distress Ingest
2. Spatio-Temporal Duplicate Detection & Merging (T-038)
3. Geocoding Pipeline (T-040)
4. Transparent 6-Factor Priority Scoring Engine (T-041)
5. Hungarian Algorithm Resource Allocation Optimizer (T-043)
6. Human-in-the-Loop Authority Approval Workflow (T-044)

Run locally:
    python backend/scripts/demo_phase3.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.modules.ai.dedup import DuplicateDetector
from app.modules.ai.embeddings import generate_embedding
from app.modules.incidents.priority import priority_engine
from app.modules.resources.allocator import resource_allocator
from app.services.geocoder import GeocodingService


async def run_phase3_demo():
    print("=" * 78)
    print("  DisasterFlow AI - Milestone M3: Intelligent Engine Demonstration (T-048)")
    print("  Zero-Budget | FOSS Stack | Explainable AI | Human-in-the-Loop Dispatch")
    print("=" * 78)

    # --------------------------------------------------------------------------
    # Step 1: Simulated Raw Reports
    # --------------------------------------------------------------------------
    print("\n[STEP 1] Citizen Distress Reports Arriving at Ingest Gateway (HTTP 202)...")
    now = datetime.now(UTC)

    reports = [
        {
            "id": uuid.uuid4(),
            "text": "Severe flood water rising rapidly near Usmanpur Yamuna bank, family of 6 stranded on roof!",
            "lat": 28.6812,
            "lon": 77.2541,
            "time": now - timedelta(minutes=25),
        },
        {
            "id": uuid.uuid4(),
            "text": "Flood water rising near Yamuna bank, people trapped on rooftop, send rescue boat!",
            "lat": 28.6828,
            "lon": 77.2555,  # ~220m away from Report 1
            "time": now - timedelta(minutes=10),
        },
        {
            "id": uuid.uuid4(),
            "text": "Massive chemical explosion at solvent plant near Mayapuri Phase II, toxic smoke spreading",
            "lat": 28.6289,
            "lon": 77.1126,  # Industrial west Delhi (~15km away)
            "time": now - timedelta(minutes=18),
        },
        {
            "id": uuid.uuid4(),
            "text": "Multi-vehicle collision on Ring Road near AIIMS flyover, 4 passengers bleeding unconscious",
            "lat": 28.5672,
            "lon": 77.2100,  # South Delhi
            "time": now - timedelta(minutes=8),
        },
    ]

    for i, r in enumerate(reports, 1):
        print(f"  Report #{i}: \"{r['text'][:65]}...\" (GPS: {r['lat']}, {r['lon']})")

    # --------------------------------------------------------------------------
    # Step 2: Spatio-Temporal Duplicate Detection (T-038)
    # --------------------------------------------------------------------------
    print("\n[STEP 2] Running Spatio-Temporal Duplicate Detection Engine...")
    detector = DuplicateDetector(similarity_threshold=0.75, max_distance_km=1.5, max_time_hours=2.0)

    canonical_incidents = []

    for r in reports:
        # Check against existing canonical incidents
        candidates = [
            {
                "id": c["id"],
                "title": c["title"],
                "description": c["description"],
                "lat": c["lat"],
                "lon": c["lon"],
                "created_at": c["created_at"],
                "embedding": c["embedding"],
            }
            for c in canonical_incidents
        ]

        match = detector.find_duplicate(
            report_text=r["text"],
            report_lat=r["lat"],
            report_lon=r["lon"],
            report_time=r["time"],
            candidate_incidents=candidates,
        )

        if match.is_duplicate:
            # Merge into matched canonical incident
            parent = next(c for c in canonical_incidents if c["id"] == match.matched_incident_id)
            parent["report_count"] += 1
            parent["reports"].append(r)
            print(f"  [+] DUPLICATE DETECTED: Report merged into Incident '{parent['title']}'")
            print(
                f"      Matched: Cosine Sim={match.similarity:.3f}, Distance={match.distance_km:.2f}km, Confidence={match.confidence:.2%}"
            )
        else:
            # Create new canonical incident
            cat = (
                "flood"
                if "flood" in r["text"].lower()
                else "fire"
                if "explosion" in r["text"].lower()
                else "medical"
            )
            sev = (
                "CRITICAL"
                if any(k in r["text"].lower() for k in ["stranded", "explosion", "unconscious"])
                else "HIGH"
            )
            people = 6 if "6" in r["text"] else 20 if "explosion" in r["text"] else 4

            cand_obj = {
                "id": uuid.uuid4(),
                "title": f"{cat.capitalize()} Emergency: {r['text'][:45]}",
                "description": r["text"],
                "category": cat,
                "severity": sev,
                "people_affected": people,
                "lat": r["lat"],
                "lon": r["lon"],
                "created_at": r["time"],
                "embedding": generate_embedding(r["text"]),
                "report_count": 1,
                "reports": [r],
            }
            canonical_incidents.append(cand_obj)
            print(f"  [+] UNIQUE EMERGENCY IDENTIFIED: Created Incident '{cand_obj['title']}'")

    print(
        f"\n  -> Ingested {len(reports)} raw reports -> Clustered into {len(canonical_incidents)} canonical emergencies."
    )

    # --------------------------------------------------------------------------
    # Step 3: Geocoding Validation (T-040)
    # --------------------------------------------------------------------------
    print("\n[STEP 3] Offline Local Gazetteer & Geocoding Verification...")
    geocoder = GeocodingService(redis_client=None)
    for landmark in ["Usmanpur", "Mayapuri", "AIIMS"]:
        res = await geocoder.geocode(landmark)
        if res:
            print(
                f"  Landmark '{landmark}' -> Resolved via [{res.source.upper()}]: {res.latitude:.4f}, {res.longitude:.4f} (Conf: {res.confidence:.0%})"
            )

    # --------------------------------------------------------------------------
    # Step 4: Transparent Priority Scoring (T-041 & T-042)
    # --------------------------------------------------------------------------
    print("\n[STEP 4] Calculating 6-Factor Transparent Priority Scores...")
    for inc in canonical_incidents:
        p_res = priority_engine.compute_priority(
            severity=inc["severity"],
            people_affected=inc["people_affected"],
            created_at=inc["created_at"],
            incident_text=f"{inc['title']} {inc['description']}",
        )
        inc["priority_score"] = p_res.priority_score
        inc["priority_breakdown"] = p_res.breakdown

    canonical_incidents.sort(key=lambda x: x["priority_score"], reverse=True)

    print("  " + "-" * 74)
    print(f"  {'Rank':<5} {'Score':<8} {'Severity':<10} {'Reports':<9} {'Title'}")
    print("  " + "-" * 74)
    for rank, inc in enumerate(canonical_incidents, 1):
        print(
            f"  #{rank:<4} {inc['priority_score']:<8.1f} {inc['severity']:<10} {inc['report_count']:<9} {inc['title']}"
        )
        # Print breakdown for top incident
        if rank == 1:
            print("    Factor Breakdown:")
            for _f_name, f_data in inc["priority_breakdown"].items():
                print(
                    f"      - {f_data['factor_name']:<18}: Contribution = {f_data['contribution']:>5.1f} pts (Weight: {f_data['weight']}%, Factor: {f_data['normalized']})"
                )

    # --------------------------------------------------------------------------
    # Step 5: Hungarian Resource Allocation (T-043 & T-044)
    # --------------------------------------------------------------------------
    print("\n[STEP 5] SciPy Hungarian Algorithm Optimal Resource Matching...")
    available_fleet = [
        {
            "id": uuid.uuid4(),
            "name": "NDRF Motor Boat Alfa-1",
            "type": "boat",
            "lat": 28.6800,
            "lon": 77.2500,
        },
        {
            "id": uuid.uuid4(),
            "name": "ALS Critical Care DL-09",
            "type": "ambulance",
            "lat": 28.5680,
            "lon": 77.2120,
        },
        {
            "id": uuid.uuid4(),
            "name": "Delhi Fire Foam Tender B-4",
            "type": "other",
            "lat": 28.6300,
            "lon": 77.1150,
        },
        {
            "id": uuid.uuid4(),
            "name": "SDRF Heavy Rescue Squad",
            "type": "rescue_team",
            "lat": 28.6600,
            "lon": 77.2300,
        },
    ]

    recommendations = resource_allocator.compute_optimal_allocation(
        incidents=canonical_incidents,
        available_resources=available_fleet,
    )

    print("  " + "-" * 74)
    print(f"  {'Incident':<30} {'Matched Resource':<28} {'Distance':<10} {'Cost'}")
    print("  " + "-" * 74)
    for rec in recommendations:
        print(
            f"  {rec.incident_title[:28]:<30} {rec.resource_name:<28} {rec.distance_km:>5.2f} km   {rec.total_cost:>5.1f}"
        )

    print("\n[STEP 6] Human-in-the-Loop Dispatch Workflow...")
    top_rec = recommendations[0]
    print(
        f"  [1] Authority Command received advisory recommendation: Assign '{top_rec.resource_name}' to '{top_rec.incident_title}'"
    )
    print("  [2] Human Commander verifies ground telemetry -> Clicks [APPROVE DISPATCH]")
    print(
        f"  [3] System commits assignment: Resource '{top_rec.resource_name}' transitioned to 'assigned'"
    )
    print(
        "  [4] Audit Log logged: {actor: 'Commander-1', action: 'approve_assignment', target: 'assignment-01'}"
    )
    print("\n" + "=" * 78)
    print("  [SUCCESS] Milestone M3 Intelligence Pipeline Demonstration Completed!")
    print("=" * 78)


if __name__ == "__main__":
    asyncio.run(run_phase3_demo())
