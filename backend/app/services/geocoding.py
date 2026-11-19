import asyncio
import hashlib
import time

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from app.core.config import settings
from app.schemas import GeocodeResponse, GeocodeResult


class NominatimGeocoder:
    def __init__(self):
        self.base_url = settings.nominatim_base_url
        self.user_agent = settings.nominatim_user_agent
        self.rate_limit = settings.nominatim_rate_limit
        self._last_request = 0.0
        self._cache: dict[str, GeocodeResponse] = {}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                headers={"User-Agent": self.user_agent},
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _cache_key(self, address: str) -> str:
        return hashlib.sha256(address.lower().strip().encode()).hexdigest()

    async def _rate_limit(self):
        elapsed = time.time() - self._last_request
        min_interval = 1.0 / self.rate_limit
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        self._last_request = time.time()

    @retry(
        wait=wait_exponential_jitter(initial=1, max=10),
        stop=stop_after_attempt(3),
    )
    async def _request(self, endpoint: str, params: dict) -> list[dict]:
        await self._rate_limit()
        client = await self._get_client()
        response = await client.get(f"{self.base_url}{endpoint}", params=params)
        response.raise_for_status()
        return response.json()

    def _parse_results(self, data: list[dict]) -> list[GeocodeResult]:
        results = []
        for item in data:
            try:
                lat = float(item["lat"])
                lon = float(item["lon"])
                address = item.get("address", {})
                results.append(
                    GeocodeResult(
                        latitude=lat,
                        longitude=lon,
                        display_name=item.get("display_name", ""),
                        confidence=self._calculate_confidence(item),
                        address_components={
                            "road": address.get("road"),
                            "house_number": address.get("house_number"),
                            "neighbourhood": address.get("neighbourhood"),
                            "suburb": address.get("suburb"),
                            "city": address.get("city") or address.get("town") or address.get("village"),
                            "state": address.get("state"),
                            "postcode": address.get("postcode"),
                            "country": address.get("country"),
                            "country_code": address.get("country_code"),
                        },
                    )
                )
            except (KeyError, ValueError):
                continue
        return results

    def _calculate_confidence(self, item: dict) -> float:
        confidence = 0.5
        if item.get("type") in ("house", "building", "address"):
            confidence += 0.3
        elif item.get("type") in ("street", "road"):
            confidence += 0.2
        if item.get("address", {}).get("house_number"):
            confidence += 0.1
        if item.get("address", {}).get("postcode"):
            confidence += 0.1
        return min(confidence, 1.0)

    async def geocode(self, address: str, country_code: str = "br") -> GeocodeResponse:
        cache_key = self._cache_key(address)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            return GeocodeResponse(results=cached.results, ambiguous=cached.ambiguous)

        params = {
            "q": address,
            "format": "json",
            "limit": 5,
            "addressdetails": 1,
            "countrycodes": country_code,
        }

        data = await self._request("/search", params)
        results = self._parse_results(data)
        ambiguous = len(results) > 1 and results[0].confidence < 0.9

        response = GeocodeResponse(results=results, ambiguous=ambiguous)
        self._cache[cache_key] = response
        return response

    async def reverse_geocode(self, latitude: float, longitude: float) -> GeocodeResult:
        cache_key = f"rev_{latitude}_{longitude}"
        if cache_key in self._cache:
            return self._cache[cache_key].results[0]

        params = {
            "lat": latitude,
            "lon": longitude,
            "format": "json",
            "addressdetails": 1,
        }

        data = await self._request("/reverse", params)
        results = self._parse_results([data])
        if results:
            self._cache[cache_key] = GeocodeResponse(results=results)
            return results[0]
        raise ValueError("No results found for coordinates")

    async def batch_geocode(self, addresses: list[str], country_code: str = "br") -> list[GeocodeResponse]:
        results = []
        for address in addresses:
            try:
                result = await self.geocode(address, country_code)
                results.append(result)
            except Exception:
                results.append(GeocodeResponse(results=[], ambiguous=False))
        return results


geocoder = NominatimGeocoder()