import asyncio
import hashlib
import json
import time

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from app.core.config import settings
from app.schemas import MatrixResponse

RATE_LIMIT_WINDOW_SECONDS = 60


class MatrixService:
    def __init__(self) -> None:
        self.base_url = settings.ors_base_url
        self.api_key = settings.ors_api_key
        self.rate_limit = settings.ors_rate_limit
        self.max_locations = settings.ors_max_locations
        self._cache: dict[str, MatrixResponse] = {}
        self._client: httpx.AsyncClient | None = None
        self._request_times: list[float] = []

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                headers=headers,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _cache_key(self, locations: list[dict], profile: str, metrics: list[str]) -> str:
        key_data = {
            "locations": [[loc["longitude"], loc["latitude"]] for loc in locations],
            "profile": profile,
            "metrics": sorted(metrics),
        }
        return hashlib.sha256(json.dumps(key_data, sort_keys=True).encode()).hexdigest()

    async def _rate_limit(self) -> None:
        now = time.time()
        self._request_times = [
            t for t in self._request_times if now - t < RATE_LIMIT_WINDOW_SECONDS
        ]
        if len(self._request_times) >= self.rate_limit:
            wait_time = RATE_LIMIT_WINDOW_SECONDS - (now - self._request_times[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)
        self._request_times.append(time.time())

    @retry(
        wait=wait_exponential_jitter(initial=1, max=10),
        stop=stop_after_attempt(3),
    )
    async def _request_matrix(
        self, locations: list[dict], profile: str, metrics: list[str]
    ) -> dict:
        await self._rate_limit()
        client = await self._get_client()

        coords = [[loc["longitude"], loc["latitude"]] for loc in locations]
        payload = {
            "locations": coords,
            "metrics": metrics,
            "units": "m",
        }

        url = f"{self.base_url}/v2/matrix/{profile}"
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def _parse_response(self, data: dict, metrics: list[str]) -> MatrixResponse:
        distances = data.get("distances", [])
        durations = data.get("durations", [])

        distances_km: list[list[float | None]] = []
        durations_min: list[list[float | None]] = []

        if "distance" in metrics:
            for row in distances:
                parsed_row: list[float | None] = []
                for d in row:
                    if d is None:
                        parsed_row.append(None)
                    else:
                        parsed_row.append(round(d / 1000.0, 3))
                distances_km.append(parsed_row)

        if "duration" in metrics:
            for row in durations:
                parsed_row: list[float | None] = []
                for d in row:
                    if d is None:
                        parsed_row.append(None)
                    else:
                        parsed_row.append(round(d / 60.0, 1))
                durations_min.append(parsed_row)

        return MatrixResponse(
            distances_km=distances_km if distances_km else [[]],
            durations_min=durations_min if durations_min else [[]],
            provider="openrouteservice",
            cached=False,
        )

    async def get_matrix(
        self,
        locations: list[dict],
        metrics: list[str] = None,
        profile: str = "driving-car",
    ) -> MatrixResponse:
        if metrics is None:
            metrics = ["distance", "duration"]

        if len(locations) > self.max_locations:
            raise ValueError(f"Maximum {self.max_locations} locations allowed per request")

        cache_key = self._cache_key(locations, profile, metrics)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            return MatrixResponse(
                distances_km=cached.distances_km,
                durations_min=cached.durations_min,
                provider=cached.provider,
                cached=True,
            )

        data = await self._request_matrix(locations, profile, metrics)
        response = self._parse_response(data, metrics)
        self._cache[cache_key] = response
        return response

    async def get_matrix_chunked(
        self,
        locations: list[dict],
        metrics: list[str] = None,
        profile: str = "driving-car",
    ) -> MatrixResponse:
        if metrics is None:
            metrics = ["distance", "duration"]

        n = len(locations)
        if n <= self.max_locations:
            return await self.get_matrix(locations, metrics, profile)

        full_distances: list[list[float | None]] = [[None] * n for _ in range(n)]
        full_durations: list[list[float | None]] = [[None] * n for _ in range(n)]

        for i in range(0, n, self.max_locations):
            for j in range(0, n, self.max_locations):
                chunk_locs = (
                    locations[i : i + self.max_locations]
                    + locations[j : j + self.max_locations]
                )
                if i == j:
                    chunk_result = await self.get_matrix(chunk_locs, metrics, profile)
                    chunk_size = len(locations[i : i + self.max_locations])
                    for r in range(chunk_size):
                        for c in range(chunk_size):
                            full_distances[i + r][j + c] = (
                                chunk_result.distances_km[r][c]
                            )
                            full_durations[i + r][j + c] = (
                                chunk_result.durations_min[r][c]
                            )
                else:
                    chunk_result = await self.get_matrix(chunk_locs, metrics, profile)
                    chunk_i_size = len(locations[i : i + self.max_locations])
                    chunk_j_size = len(locations[j : j + self.max_locations])
                    for r in range(chunk_i_size):
                        for c in range(chunk_j_size):
                            full_distances[i + r][j + c] = (
                                chunk_result.distances_km[r][chunk_i_size + c]
                            )
                            full_durations[i + r][j + c] = (
                                chunk_result.durations_min[r][chunk_i_size + c]
                            )

        return MatrixResponse(
            distances_km=full_distances,
            durations_min=full_durations,
            provider="openrouteservice",
            cached=False,
        )


matrix_service = MatrixService()