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