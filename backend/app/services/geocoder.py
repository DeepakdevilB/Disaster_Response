"""Nominatim geocoding client with Redis caching and local gazetteer fallback (T-040).

Adheres to OpenStreetMap's Nominatim usage policy (identifying User-Agent, max 1 req/sec).
Provides an offline local gazetteer so tests, demos, and air-gapped environments resolve
localities without network calls or external API bills.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "DisasterFlow-EmergencyCoordinator/1.0 (Final-Year B.Tech Major Project; student-team)"
CACHE_TTL_SECONDS = 86400  # 24 hours

# In-memory LRU cache fallback if Redis is unavailable
_MEMORY_GEO_CACHE: dict[str, GeocodeResult] = {}
_LAST_NOMINATIM_REQUEST_TIME = 0.0

# Local Gazetteer for offline emergency triage (Delhi NCR and common crisis scenario landmarks)
LOCAL_GAZETTEER: dict[str, tuple[float, float, str]] = {
    "usmanpur": (28.6812, 77.2541, "Usmanpur, Yamuna Bank, Delhi"),
    "yamuna bank": (28.6219, 77.2655, "Yamuna Bank, Delhi"),
    "mayapuri": (28.6289, 77.1126, "Mayapuri Industrial Area, Delhi"),
    "aiims": (28.5672, 77.2100, "AIIMS, Ring Road, New Delhi"),
    "dhaula kuan": (28.5921, 77.1563, "Dhaula Kuan, New Delhi"),
    "chandni chowk": (28.6562, 77.2307, "Chandni Chowk, Old Delhi"),
    "rohini": (28.7180, 77.1320, "Rohini Sector 14, Delhi"),
    "civil lines": (28.6750, 77.2250, "Civil Lines, North Delhi"),
    "connaught place": (28.6315, 77.2167, "Connaught Place, Central Delhi"),
    "anand vihar": (28.6469, 77.3160, "Anand Vihar ISBT, East Delhi"),
    "kashmere gate": (28.6675, 77.2285, "Kashmere Gate Metro, Delhi"),
    "noida sector 18": (28.5708, 77.3260, "Noida Sector 18, UP"),
    "gurugram cyber city": (28.4950, 77.0890, "Cyber City, Gurugram, Haryana"),
    "saket": (28.5244, 77.2102, "Saket District Centre, South Delhi"),
    "okhla": (28.5355, 77.2732, "Okhla Industrial Area, Delhi"),
}


@dataclass
class GeocodeResult:
    """Geocoded coordinate result."""

    latitude: float
    longitude: float
    display_name: str
    source: str  # "redis_cache", "nominatim", "gazetteer", or "unknown"
    confidence: float


class GeocodingService:
    """Geocoding service with rate limiting, caching, and gazetteer fallback."""

    def __init__(self, redis_client: Any = None) -> None:
        self.redis = redis_client

    async def geocode(self, location_phrase: str) -> GeocodeResult | None:
        """Geocode a text location into lat/lon coordinates."""
        if not location_phrase or not location_phrase.strip():
            return None

        clean_query = location_phrase.strip().lower()
        cache_key = f"geocode:{clean_query}"

        # 1. Check Redis cache if available
        if self.redis is not None:
            try:
                cached = await self.redis.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    return GeocodeResult(
                        latitude=data["latitude"],
                        longitude=data["longitude"],
                        display_name=data["display_name"],
                        source="redis_cache",
                        confidence=data.get("confidence", 0.95),
                    )
            except Exception as exc:
                logger.debug("Redis cache read skipped: %s", exc)

        # 2. Check in-memory memory cache
        if clean_query in _MEMORY_GEO_CACHE:
            return _MEMORY_GEO_CACHE[clean_query]

        # 3. Check offline Local Gazetteer first for known key localities
        for keyword, (lat, lon, name) in LOCAL_GAZETTEER.items():
            if keyword in clean_query:
                result = GeocodeResult(
                    latitude=lat,
                    longitude=lon,
                    display_name=name,
                    source="gazetteer",
                    confidence=0.98,
                )
                self._save_to_cache(clean_query, cache_key, result)
                return result

        # 4. Attempt OpenStreetMap Nominatim with 1 req/sec rate limit
        global _LAST_NOMINATIM_REQUEST_TIME
        now = time.time()
        elapsed = now - _LAST_NOMINATIM_REQUEST_TIME
        if elapsed < 1.0:
            # Enforce 1 second delay per OSM policy
            await _async_sleep(1.0 - elapsed)

        try:
            _LAST_NOMINATIM_REQUEST_TIME = time.time()
            async with httpx.AsyncClient(timeout=4.0) as client:
                headers = {"User-Agent": USER_AGENT}
                params = {"q": clean_query, "format": "json", "limit": 1}
                resp = await client.get(NOMINATIM_URL, params=params, headers=headers)

                if resp.status_code == 200:
                    data = resp.json()
                    if data and len(data) > 0:
                        top = data[0]
                        result = GeocodeResult(
                            latitude=float(top["lat"]),
                            longitude=float(top["lon"]),
                            display_name=top.get("display_name", clean_query),
                            source="nominatim",
                            confidence=0.90,
                        )
                        self._save_to_cache(clean_query, cache_key, result)
                        return result
        except Exception as exc:
            logger.warning("Nominatim geocoding failed for '%s': %s", clean_query, exc)

        return None

    def _save_to_cache(self, clean_query: str, cache_key: str, result: GeocodeResult) -> None:
        """Store result in memory and Redis cache."""
        _MEMORY_GEO_CACHE[clean_query] = result
        if self.redis is not None:
            try:
                payload = json.dumps(
                    {
                        "latitude": result.latitude,
                        "longitude": result.longitude,
                        "display_name": result.display_name,
                        "confidence": result.confidence,
                    }
                )
                self.redis.set(cache_key, payload, ex=CACHE_TTL_SECONDS)
            except Exception as exc:
                logger.debug("Redis cache write skipped: %s", exc)


async def _async_sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)
