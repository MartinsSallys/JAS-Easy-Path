from unittest.mock import AsyncMock, patch

import pytest

from app.schemas import MatrixResponse
from app.services.matrix import MatrixService

LOCATION_COUNT = 3
EXPECTED_DISTANCE_KM = 5.2
EXPECTED_DURATION_MIN = 8.0
CHUNKED_LOCATION_COUNT = 51


@pytest.fixture
def matrix_service() -> MatrixService:
    return MatrixService()


@pytest.fixture
def mock_ors_response() -> dict:
    return {
        "distances": [
            [0, 5200, 8100],
            [5200, 0, 3400],
            [8100, 3400, 0],
        ],
        "durations": [
            [0, 480, 720],
            [480, 0, 240],
            [720, 240, 0],
        ],
        "metadata": {
            "attribution": "openrouteservice.org | OpenStreetMap contributors",
            "units": "m",
        },
    }


@pytest.mark.asyncio
async def test_get_matrix_success(matrix_service: MatrixService, mock_ors_response) -> None:
    locations = [
        {"latitude": -23.5617, "longitude": -46.6560},
        {"latitude": -23.5505, "longitude": -46.6333},
        {"latitude": -23.5550, "longitude": -46.6400},
    ]

    with patch.object(matrix_service, "_request_matrix", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_ors_response

        response = await matrix_service.get_matrix(locations)

    assert isinstance(response, MatrixResponse)
    assert response.provider == "openrouteservice"
    assert response.cached is False
    assert len(response.distances_km) == LOCATION_COUNT
    assert len(response.distances_km[0]) == LOCATION_COUNT
    # Check conversion from meters to km
    assert response.distances_km[0][1] == EXPECTED_DISTANCE_KM  # 5200m = 5.2km
    assert response.durations_min[0][1] == EXPECTED_DURATION_MIN  # 480s = 8.0min


@pytest.mark.asyncio
async def test_get_matrix_cached(matrix_service: MatrixService, mock_ors_response) -> None:
    locations = [
        {"latitude": -23.5617, "longitude": -46.6560},
        {"latitude": -23.5505, "longitude": -46.6333},
    ]

    with patch.object(matrix_service, "_request_matrix", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_ors_response

        # First call
        response1 = await matrix_service.get_matrix(locations)
        # Second call should use cache
        response2 = await matrix_service.get_matrix(locations)

    assert response1.cached is False
    assert response2.cached is True
    assert response1.distances_km == response2.distances_km


@pytest.mark.asyncio
async def test_get_matrix_km_units(matrix_service: MatrixService) -> None:
    """Test parsing when ORS returns km instead of m."""
    response_data = {
        "distances": [
            [0, 5.2, 8.1],
            [5.2, 0, 3.4],
            [8.1, 3.4, 0],
        ],
        "durations": [
            [0, 480, 720],
            [480, 0, 240],
            [720, 240, 0],
        ],
        "metadata": {
            "units": "km",
        },
    }

    locations = [
        {"latitude": -23.5617, "longitude": -46.6560},
        {"latitude": -23.5505, "longitude": -46.6333},
        {"latitude": -23.5550, "longitude": -46.6400},
    ]

    with patch.object(matrix_service, "_request_matrix", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = response_data

        response = await matrix_service.get_matrix(locations)

    assert response.distances_km[0][1] == EXPECTED_DISTANCE_KM  # Already in km


@pytest.mark.asyncio
async def test_get_matrix_null_values(matrix_service: MatrixService) -> None:
    """Test that null values in response are preserved as None."""
    response_data = {
        "distances": [
            [0, 5200, None],
            [5200, 0, 3400],
            [None, 3400, 0],
        ],
        "durations": [
            [0, 480, None],
            [480, 0, 240],
            [None, 240, 0],
        ],
        "metadata": {"units": "m"},
    }

    locations = [
        {"latitude": -23.5617, "longitude": -46.6560},
        {"latitude": -23.5505, "longitude": -46.6333},
        {"latitude": -23.5550, "longitude": -46.6400},
    ]

    with patch.object(matrix_service, "_request_matrix", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = response_data

        response = await matrix_service.get_matrix(locations)

    assert response.distances_km[0][2] is None
    assert response.distances_km[2][0] is None
    assert response.durations_min[0][2] is None


@pytest.mark.asyncio
async def test_get_matrix_missing_distances_raises(matrix_service: MatrixService) -> None:
    """Test that missing distances field raises ValueError."""
    response_data = {
        "durations": [[0, 480], [480, 0]],
        "metadata": {"units": "m"},
    }

    locations = [
        {"latitude": -23.5617, "longitude": -46.6560},
        {"latitude": -23.5505, "longitude": -46.6333},
    ]

    with patch.object(matrix_service, "_request_matrix", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = response_data

        with pytest.raises(ValueError, match="missing 'distances'"):
            await matrix_service.get_matrix(locations)


@pytest.mark.asyncio
async def test_get_matrix_unknown_units_raises(matrix_service: MatrixService) -> None:
    """Test that unknown units raises ValueError."""
    response_data = {
        "distances": [[0, 5200], [5200, 0]],
        "durations": [[0, 480], [480, 0]],
        "metadata": {"units": "miles"},
    }

    locations = [
        {"latitude": -23.5617, "longitude": -46.6560},
        {"latitude": -23.5505, "longitude": -46.6333},
    ]

    with patch.object(matrix_service, "_request_matrix", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = response_data

        with pytest.raises(ValueError, match="Unknown unit from ORS"):
            await matrix_service.get_matrix(locations)


@pytest.mark.asyncio
async def test_get_matrix_chunked_under_limit(
    matrix_service: MatrixService, mock_ors_response
) -> None:
    """Test chunked falls back to get_matrix when under limit."""
    locations = [
        {"latitude": -23.5617, "longitude": -46.6560},
        {"latitude": -23.5505, "longitude": -46.6333},
    ]

    with patch.object(matrix_service, "get_matrix", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MatrixResponse(
            distances_km=[[0, 5.2], [5.2, 0]],
            durations_min=[[0, 8.0], [8.0, 0]],
            provider="openrouteservice",
            cached=False,
        )

        response = await matrix_service.get_matrix_chunked(locations)

    assert response.distances_km == [[0, 5.2], [5.2, 0]]


@pytest.mark.asyncio
async def test_get_matrix_chunked_over_limit(matrix_service: MatrixService) -> None:
    """Test chunked matrix with 51 locations (over 50 limit)."""
    # Create 51 locations
    locations = [
        {"latitude": -23.5617 + i * 0.001, "longitude": -46.6560 + i * 0.001}
        for i in range(51)
    ]

    async def mock_get_matrix(locs, metrics, profile) -> MatrixResponse:  # noqa: ANN001
        size = len(locs)
        distances = [[float(abs(i - j) * 1000) for j in range(size)] for i in range(size)]
        durations = [[float(abs(i - j) * 60) for j in range(size)] for i in range(size)]
        return MatrixResponse(
            distances_km=[[d / 1000 for d in row] for row in distances],
            durations_min=[[d / 60 for d in row] for row in durations],
            provider="openrouteservice",
            cached=False,
        )

    with patch.object(matrix_service, "get_matrix", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = mock_get_matrix

        response = await matrix_service.get_matrix_chunked(locations)

    assert len(response.distances_km) == CHUNKED_LOCATION_COUNT
    assert len(response.distances_km[0]) == CHUNKED_LOCATION_COUNT
    assert len(response.durations_min) == CHUNKED_LOCATION_COUNT
    assert len(response.durations_min[0]) == CHUNKED_LOCATION_COUNT
    # Diagonal should be 0
    for i in range(CHUNKED_LOCATION_COUNT):
        assert response.distances_km[i][i] == 0.0
        assert response.durations_min[i][i] == 0.0
    # Cross-chunk entries should be filled
    assert response.distances_km[0][50] is not None
    assert response.distances_km[50][0] is not None


@pytest.mark.asyncio
async def test_get_matrix_chunked_symmetric(matrix_service: MatrixService) -> None:
    """Test that chunked matrix produces symmetric results."""
    locations = [
        {"latitude": -23.5617 + i * 0.001, "longitude": -46.6560 + i * 0.001}
        for i in range(55)
    ]

    async def mock_get_matrix(locs, metrics, profile) -> MatrixResponse:  # noqa: ANN001
        size = len(locs)
        distances = [[float(abs(i - j) * 1000) for j in range(size)] for i in range(size)]
        durations = [[float(abs(i - j) * 60) for j in range(size)] for i in range(size)]
        return MatrixResponse(
            distances_km=[[d / 1000 for d in row] for row in distances],
            durations_min=[[d / 60 for d in row] for row in durations],
            provider="openrouteservice",
            cached=False,
        )

    with patch.object(matrix_service, "get_matrix", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = mock_get_matrix

        response = await matrix_service.get_matrix_chunked(locations)

    n = 55
    for i in range(n):
        for j in range(n):
            assert response.distances_km[i][j] == response.distances_km[j][i]
            assert response.durations_min[i][j] == response.durations_min[j][i]