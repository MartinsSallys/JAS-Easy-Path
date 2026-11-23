
from unittest.mock import patch

import pytest
from ortools.constraint_solver import routing_enums_pb2
from route_engine import SolveResult, SolverStatus

from app.schemas import (
    OptimizationDelivery,
    OptimizationLocation,
    OptimizationRequest,
    OptimizationVehicle,
)
from app.services.optimizer import (
    HaversineMatrixProvider,
    RouteEngineAdapter,
)

MIN_STOPS_IN_ROUTE = 3  # depot + at least 1 delivery + depot
DELIVERY_ID = 10
EXPECTED_LOAD_AFTER = 5
SERVICE_TIME_MIN = 8


TEST_TIME_LIMIT_SECONDS = 5


@pytest.fixture
def optimizer() -> RouteEngineAdapter:
    return RouteEngineAdapter(time_limit_seconds=TEST_TIME_LIMIT_SECONDS)


def _hhmm_to_minutes(value: str) -> int:
    hours, minutes = (int(part) for part in value.split(":"))
    return hours * 60 + minutes


def test_simple_cvrp(optimizer: RouteEngineAdapter) -> None:
    depot = OptimizationLocation(
        latitude=-23.5617, longitude=-46.6560, address="Depot"
    )
    vehicles = [OptimizationVehicle(id=1, capacity=20)]
    deliveries = [
        OptimizationDelivery(
            id=DELIVERY_ID + i,
            demand=demand,
            location=OptimizationLocation(
                latitude=-23.5505 - i * 0.005,
                longitude=-46.6333 - i * 0.004,
                address=f"Delivery {i}",
            ),
        )
        for i, demand in enumerate([3, 5, 2, 4, 6])
    ]

    request = OptimizationRequest(depot=depot, vehicles=vehicles, deliveries=deliveries)
    response = optimizer.solve(request)

    assert response.status == "feasible"
    assert len(response.routes) == 1
    assert response.routes[0].vehicle_id == 1
    assert response.routes[0].total_load == sum(d.demand for d in deliveries)
    assert len(response.routes[0].stops) == len(deliveries) + 2  # + depot ends
    assert response.unassigned == []


def test_capacity_exceeded_is_infeasible(optimizer: RouteEngineAdapter) -> None:
    """Over-capacity input is rejected as infeasible (all-or-nothing engine)."""
    depot = OptimizationLocation(
        latitude=-23.5617, longitude=-46.6560, address="Depot"
    )
    vehicles = [OptimizationVehicle(id=1, capacity=10)]
    deliveries = [
        OptimizationDelivery(
            id=DELIVERY_ID + i,
            demand=demand,
            location=OptimizationLocation(
                latitude=-23.5505 - i * 0.005, longitude=-46.6333 - i * 0.007
            ),
        )
        for i, demand in enumerate([6, 7])
    ]

    request = OptimizationRequest(depot=depot, vehicles=vehicles, deliveries=deliveries)
    response = optimizer.solve(request)

    # Engine has no partial assignment: infeasible with every delivery unassigned
    assert response.status == "infeasible"
    assert len(response.unassigned) == len(deliveries)
    assert response.routes == []


def test_time_window_shorter_than_service_is_infeasible(
    optimizer: RouteEngineAdapter,
) -> None:
    """A 1-minute window (09:00-09:01) cannot fit the 8-minute service."""
    depot = OptimizationLocation(
        latitude=-23.5617, longitude=-46.6560, address="Depot"
    )
    vehicles = [OptimizationVehicle(id=1, capacity=20)]
    deliveries = [
        OptimizationDelivery(
            id=DELIVERY_ID,
            demand=3,
            location=OptimizationLocation(
                latitude=-23.5505, longitude=-46.6333, address="Delivery 1"
            ),
            time_window_start="09:00",
            time_window_end="09:01",
        ),
    ]

    request = OptimizationRequest(depot=depot, vehicles=vehicles, deliveries=deliveries)
    response = optimizer.solve(request)

    assert response.status == "infeasible"
    assert len(response.unassigned) == 1
    assert response.unassigned[0].id == DELIVERY_ID
    assert len(response.routes) == 0


def test_time_window_feasible_applies_service_time(
    optimizer: RouteEngineAdapter,
) -> None:
    """Service takes exactly 8 minutes within the delivery window."""
    depot = OptimizationLocation(
        latitude=-23.5617, longitude=-46.6560, address="Depot"
    )
    vehicles = [OptimizationVehicle(id=1, capacity=20)]
    deliveries = [
        OptimizationDelivery(
            id=DELIVERY_ID,
            demand=3,
            location=OptimizationLocation(
                latitude=-23.5505, longitude=-46.6333, address="Delivery 1"
            ),
            time_window_start="08:00",
            time_window_end="12:00",
        ),
    ]

    request = OptimizationRequest(depot=depot, vehicles=vehicles, deliveries=deliveries)
    response = optimizer.solve(request)

    assert response.status == "feasible"
    assert len(response.unassigned) == 0
    assert len(response.routes) == 1
    stops = response.routes[0].stops
    delivery_stop = next(s for s in stops if s.delivery_id == DELIVERY_ID)
    assert delivery_stop.arrival_time is not None
    assert delivery_stop.departure_time is not None
    service = _hhmm_to_minutes(delivery_stop.departure_time) - _hhmm_to_minutes(
        delivery_stop.arrival_time
    )
    assert service == SERVICE_TIME_MIN
    # Whole attendance stays inside the window
    assert delivery_stop.arrival_time >= "08:00"
    assert delivery_stop.departure_time <= "12:00"


def test_return_depot_included_in_distance(optimizer: RouteEngineAdapter) -> None:
    """Total distance is the round trip depot -> delivery -> depot."""
    depot = OptimizationLocation(
        latitude=-23.5617, longitude=-46.6560, address="Depot"
    )
    delivery_location = OptimizationLocation(
        latitude=-23.5505, longitude=-46.6333, address="Delivery 1"
    )
    vehicles = [OptimizationVehicle(id=1, capacity=20)]
    deliveries = [
        OptimizationDelivery(id=DELIVERY_ID, demand=3, location=delivery_location),
    ]

    request = OptimizationRequest(depot=depot, vehicles=vehicles, deliveries=deliveries)
    response = optimizer.solve(request)

    assert response.status == "feasible"
    route = response.routes[0]
    distances, _ = HaversineMatrixProvider().build([depot, delivery_location])
    expected_km = round(2 * distances[0][1] / 1000, 2)
    assert route.total_distance_km == expected_km

    stops = route.stops
    assert stops[0].delivery_id is None  # start depot
    assert stops[-1].delivery_id is None  # end depot
    assert len(stops) >= MIN_STOPS_IN_ROUTE


def test_load_after_reflects_delivery_demand(optimizer: RouteEngineAdapter) -> None:
    """load_after accumulates demand; the final depot stop unloads to 0."""
    depot = OptimizationLocation(
        latitude=-23.5617, longitude=-46.6560, address="Depot"
    )
    vehicles = [OptimizationVehicle(id=1, capacity=20)]
    deliveries = [
        OptimizationDelivery(
            id=DELIVERY_ID,
            demand=EXPECTED_LOAD_AFTER,
            location=OptimizationLocation(
                latitude=-23.5505, longitude=-46.6333, address="Delivery 1"
            ),
        ),
    ]

    request = OptimizationRequest(depot=depot, vehicles=vehicles, deliveries=deliveries)
    response = optimizer.solve(request)

    assert response.status == "feasible"
    route = response.routes[0]
    stops = route.stops
    delivery_stop = next(s for s in stops if s.delivery_id == DELIVERY_ID)
    assert delivery_stop.load_after == EXPECTED_LOAD_AFTER
    return_stop = stops[-1]
    assert return_stop.load_after == 0
    assert return_stop.delivery_id is None


def test_work_hours_respected(optimizer: RouteEngineAdapter) -> None:
    """A delivery too far to serve within 08:00-18:00 is infeasible."""
    depot = OptimizationLocation(
        latitude=-23.5617, longitude=-46.6560, address="Depot"
    )
    vehicles = [OptimizationVehicle(id=1, capacity=20)]
    deliveries = [
        OptimizationDelivery(
            id=DELIVERY_ID,
            demand=3,
            location=OptimizationLocation(
                latitude=-25.0, longitude=-48.0, address="Far Delivery"
            ),
        ),
    ]

    request = OptimizationRequest(depot=depot, vehicles=vehicles, deliveries=deliveries)
    response = optimizer.solve(request)

    assert response.status == "infeasible"
    assert len(response.unassigned) == 1
    assert response.unassigned[0].id == DELIVERY_ID


class _ManualMatrixProvider:
    """Provider com matrizes manuais (metros/minutos) para testes determinísticos."""

    def __init__(
        self, distances_m: list[list[int]], durations_min: list[list[int]]
    ) -> None:
        self._distances = distances_m
        self._durations = durations_min

    def build(self, locations):  # noqa: ANN001, ANN202
        return self._distances, self._durations


def test_injected_matrix_provider_controls_route() -> None:
    """An injected provider lets tests control the cost matrix exactly."""
    depot = OptimizationLocation(
        latitude=-23.5, longitude=-46.6, address="Depot"
    )
    near = OptimizationLocation(latitude=-23.51, longitude=-46.61, address="Near")
    far = OptimizationLocation(latitude=-23.52, longitude=-46.62, address="Far")
    deliveries = [
        OptimizationDelivery(id=10, demand=1, location=far),
        OptimizationDelivery(id=11, demand=1, location=near),
    ]
    # depot=0, far=1, near=2: cheapest order is depot -> near(11) -> far(10) -> depot
    distances = [
        [0, 3000, 1000],
        [3000, 0, 1000],
        [1000, 1000, 0],
    ]
    durations = [
        [0, 30, 10],
        [30, 0, 10],
        [10, 10, 0],
    ]
    adapter = RouteEngineAdapter(
        matrix_provider=_ManualMatrixProvider(distances, durations),
        time_limit_seconds=TEST_TIME_LIMIT_SECONDS,
    )

    request = OptimizationRequest(
        depot=depot,
        vehicles=[OptimizationVehicle(id=1, capacity=10)],
        deliveries=deliveries,
    )
    response = adapter.solve(request)

    assert response.status == "feasible"
    route = response.routes[0]
    delivery_order = [s.delivery_id for s in route.stops if s.delivery_id is not None]
    assert delivery_order == [11, 10]
    assert route.total_distance_km == round(
        (distances[0][2] + distances[2][1] + distances[1][0]) / 1000, 2
    )


def _single_delivery_request(**delivery_kwargs: object) -> OptimizationRequest:
    depot = OptimizationLocation(latitude=-23.5617, longitude=-46.6560)
    return OptimizationRequest(
        depot=depot,
        vehicles=[OptimizationVehicle(id=1, capacity=20)],
        deliveries=[
            OptimizationDelivery(
                id=DELIVERY_ID,
                demand=3,
                location=OptimizationLocation(
                    latitude=-23.5505, longitude=-46.6333
                ),
                **delivery_kwargs,
            )
        ],
    )


def test_malformed_input_is_invalid_input(optimizer: RouteEngineAdapter) -> None:
    """Horário fora do formato HH:MM é entrada inválida, não inviabilidade."""
    request = _single_delivery_request(
        time_window_start="25:00", time_window_end="12:00"
    )

    response = optimizer.solve(request)

    assert response.status == "invalid_input"
    assert response.message is not None
    assert response.routes == []
    assert len(response.unassigned) == 1


def test_infeasible_input_carries_reason(optimizer: RouteEngineAdapter) -> None:
    """Janela sem espaço para o atendimento é inviabilidade comprovada."""
    request = _single_delivery_request(
        time_window_start="09:00", time_window_end="09:05"
    )

    response = optimizer.solve(request)

    assert response.status == "infeasible"
    assert "atendimento" in (response.message or "")
    assert response.routes == []


@pytest.mark.parametrize(
    "delivery_kwargs",
    [
        {"time_window_start": "17:00"},
        {"time_window_end": "12:00"},
    ],
)
def test_partial_time_window_is_invalid_input(
    optimizer: RouteEngineAdapter, delivery_kwargs: dict
) -> None:
    """Janela pela metade não é descartada: o motor a rejeita como invalid_input."""
    request = _single_delivery_request(**delivery_kwargs)

    response = optimizer.solve(request)

    assert response.status == "invalid_input"
    assert response.message is not None
    assert response.routes == []
    assert len(response.unassigned) == 1


_ROUTING_STATUS = routing_enums_pb2.RoutingSearchStatus


@pytest.mark.parametrize(
    ("solver_status", "ortools_code", "expected"),
    [
        (_ROUTING_STATUS.ROUTING_INFEASIBLE, SolverStatus.INFEASIBLE, "infeasible"),
        (_ROUTING_STATUS.ROUTING_INVALID, SolverStatus.INVALID_MODEL, "invalid_model"),
        (_ROUTING_STATUS.ROUTING_FAIL, SolverStatus.NO_SOLUTION, "no_solution"),
        (_ROUTING_STATUS.ROUTING_FAIL_TIMEOUT, SolverStatus.NO_SOLUTION, "timeout"),
    ],
)
def test_solver_failure_statuses_are_distinct(
    optimizer: RouteEngineAdapter,
    solver_status: int,
    ortools_code: SolverStatus,
    expected: str,
) -> None:
    """O adapter preserva inviável, modelo inválido, sem solução e timeout."""
    request = _single_delivery_request()
    result = SolveResult(
        status=ortools_code,
        routes=None,
        total_distance_meters=None,
        ortools_status_code=solver_status,
    )

    with patch("app.services.optimizer.solve_routes", return_value=result):
        response = optimizer.solve(request)

    assert response.status == expected
    assert response.routes == []
    assert len(response.unassigned) == 1
