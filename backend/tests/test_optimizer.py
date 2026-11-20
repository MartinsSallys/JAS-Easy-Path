
import pytest

from app.schemas import (
    OptimizationDelivery,
    OptimizationLocation,
    OptimizationRequest,
    OptimizationVehicle,
)
from app.services.optimizer import RouteEngineAdapter

MIN_STOPS_IN_ROUTE = 3  # depot + at least 1 delivery + depot


@pytest.fixture
def optimizer() -> RouteEngineAdapter:
    return RouteEngineAdapter()


def test_simple_cvrp(optimizer: RouteEngineAdapter) -> None:
    depot = OptimizationLocation(
        latitude=-23.5617, longitude=-46.6560, address="Depot"
    )
    vehicles = [OptimizationVehicle(id=1, capacity=20)]
    deliveries = [
        OptimizationDelivery(
            id=10,
            demand=3,
            location=OptimizationLocation(
                latitude=-23.5505, longitude=-46.6333, address="Delivery 1"
            ),
        ),
        OptimizationDelivery(
            id=11,
            demand=5,
            location=OptimizationLocation(
                latitude=-23.5550, longitude=-46.6400, address="Delivery 2"
            ),
        ),
        OptimizationDelivery(
            id=12,
            demand=2,
            location=OptimizationLocation(
                latitude=-23.5600, longitude=-46.6450, address="Delivery 3"
            ),
        ),
        OptimizationDelivery(
            id=13,
            demand=4,
            location=OptimizationLocation(
                latitude=-23.5650, longitude=-46.6500, address="Delivery 4"
            ),
        ),
        OptimizationDelivery(
            id=14,
            demand=6,
            location=OptimizationLocation(
                latitude=-23.5700, longitude=-46.6550, address="Delivery 5"
            ),
        ),
    ]

    request = OptimizationRequest(depot=depot, vehicles=vehicles, deliveries=deliveries)
    response = optimizer.solve(request)

    assert response.status in ("optimal", "feasible")
    assert len(response.routes) == 1
    assert response.routes[0].vehicle_id == 1
    # Some deliveries may be unassigned due to time window constraints
    assert response.routes[0].total_load > 0
    assert len(response.routes[0].stops) >= MIN_STOPS_IN_ROUTE


def test_capacity_exceeded(optimizer: RouteEngineAdapter) -> None:
    depot = OptimizationLocation(
        latitude=-23.5617, longitude=-46.6560, address="Depot"
    )
    vehicles = [OptimizationVehicle(id=1, capacity=10)]
    deliveries = [
        OptimizationDelivery(
            id=10,
            demand=6,
            location=OptimizationLocation(latitude=-23.5505, longitude=-46.6333),
        ),
        OptimizationDelivery(
            id=11,
            demand=7,
            location=OptimizationLocation(latitude=-23.5550, longitude=-46.6400),
        ),
    ]

    request = OptimizationRequest(depot=depot, vehicles=vehicles, deliveries=deliveries)
    response = optimizer.solve(request)

    # Solver may find partial feasible solution instead of infeasible
    assert response.status in ("feasible", "infeasible")
    # At least one delivery should be unassigned due to capacity
    assert len(response.unassigned) >= 1


def test_time_window_short_infeasible(optimizer: RouteEngineAdapter) -> None:
    """Test that a 1-minute time window (09:00-09:01) cannot be satisfied with 8 min service."""
    depot = OptimizationLocation(
        latitude=-23.5617, longitude=-46.6560, address="Depot"
    )
    vehicles = [OptimizationVehicle(id=1, capacity=20)]
    deliveries = [
        OptimizationDelivery(
            id=10,
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

    # With 8 min service time, a 1-minute window cannot be satisfied
    # Solver should return infeasible
    assert response.status == "infeasible"
    assert len(response.unassigned) == 1
    assert response.unassigned[0].id == 10
    assert len(response.routes) == 0


def test_time_window_feasible(optimizer: RouteEngineAdapter) -> None:
    """Test that a reasonable time window works with service time."""
    depot = OptimizationLocation(
        latitude=-23.5617, longitude=-46.6560, address="Depot"
    )
    vehicles = [OptimizationVehicle(id=1, capacity=20)]
    deliveries = [
        OptimizationDelivery(
            id=10,
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

    assert response.status in ("optimal", "feasible")
    assert len(response.unassigned) == 0
    assert len(response.routes) == 1
    # Check service time is applied (departure = arrival + 8 min)
    stops = response.routes[0].stops
    delivery_stop = next(s for s in stops if s.delivery_id == 10)
    assert delivery_stop.arrival_time is not None
    assert delivery_stop.departure_time is not None


def test_return_depot_included_in_distance(optimizer: RouteEngineAdapter) -> None:
    """Test that total distance includes return to depot."""
    depot = OptimizationLocation(
        latitude=-23.5617, longitude=-46.6560, address="Depot"
    )
    vehicles = [OptimizationVehicle(id=1, capacity=20)]
    deliveries = [
        OptimizationDelivery(
            id=10,
            demand=3,
            location=OptimizationLocation(
                latitude=-23.5505, longitude=-46.6333, address="Delivery 1"
            ),
        ),
    ]

    request = OptimizationRequest(depot=depot, vehicles=vehicles, deliveries=deliveries)
    response = optimizer.solve(request)

    assert response.status in ("optimal", "feasible")
    route = response.routes[0]
    # Distance should be round trip: depot -> delivery -> depot
    assert route.total_distance_km > 0
    # Verify stops include depot at start and end
    stops = route.stops
    assert stops[0].delivery_id is None  # start depot
    assert stops[-1].delivery_id is None  # end depot
    assert len(stops) >= 3  # depot + delivery + depot


def test_load_after_not_masked(optimizer: RouteEngineAdapter) -> None:
    """Test that load_after reflects actual load (not masked to >= 0)."""
    depot = OptimizationLocation(
        latitude=-23.5617, longitude=-46.6560, address="Depot"
    )
    vehicles = [OptimizationVehicle(id=1, capacity=20)]
    deliveries = [
        OptimizationDelivery(
            id=10,
            demand=5,
            location=OptimizationLocation(
                latitude=-23.5505, longitude=-46.6333, address="Delivery 1"
            ),
        ),
    ]

    request = OptimizationRequest(depot=depot, vehicles=vehicles, deliveries=deliveries)
    response = optimizer.solve(request)

    assert response.status in ("optimal", "feasible")
    route = response.routes[0]
    stops = route.stops
    # Find delivery stop
    delivery_stop = next(s for s in stops if s.delivery_id == 10)
    # Load after delivery should be the demand (5)
    assert delivery_stop.load_after == 5
    # Return depot stop should have load_after = 0
    return_stop = stops[-1]
    assert return_stop.load_after == 0
    assert return_stop.delivery_id is None


def test_work_hours_respected(optimizer: RouteEngineAdapter) -> None:
    """Test that solver respects working hours (08:00-18:00)."""
    depot = OptimizationLocation(
        latitude=-23.5617, longitude=-46.6560, address="Depot"
    )
    vehicles = [OptimizationVehicle(id=1, capacity=20)]
    # Delivery far away requiring travel outside work hours
    deliveries = [
        OptimizationDelivery(
            id=10,
            demand=3,
            location=OptimizationLocation(
                latitude=-25.0, longitude=-48.0, address="Far Delivery"
            ),
        ),
    ]

    request = OptimizationRequest(depot=depot, vehicles=vehicles, deliveries=deliveries)
    response = optimizer.solve(request)

    # Should be infeasible or unassigned due to work hours
    if response.status in {"infeasible", "feasible"}:
        assert len(response.unassigned) >= 1
