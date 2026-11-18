from route_engine.domain.models import Delivery, Depot, Location, Problem, Vehicle


def make_problem(
    *,
    vehicles: tuple[Vehicle, ...] = (),
    deliveries: tuple[Delivery, ...] = (),
) -> Problem:
    depot = Depot(id=0, location=Location(latitude=0, longitude=0))
    return Problem(depot=depot, vehicles=vehicles, deliveries=deliveries)


def make_delivery(delivery_id: int, demand: int) -> Delivery:
    location = Location(latitude=0, longitude=0)
    return Delivery(id=delivery_id, demand=demand, location=location)


def test_total_demand_sums_all_delivery_demands() -> None:
    problem = make_problem(
        deliveries=(
            make_delivery(delivery_id=1, demand=3),
            make_delivery(delivery_id=2, demand=4),
            make_delivery(delivery_id=3, demand=6),
        )
    )

    assert problem.total_demand == 13


def test_total_demand_is_zero_without_deliveries() -> None:
    problem = make_problem()

    assert problem.total_demand == 0


def test_total_capacity_sums_all_vehicle_capacities() -> None:
    problem = make_problem(
        vehicles=(
            Vehicle(id=1, capacity=10),
            Vehicle(id=2, capacity=15),
            Vehicle(id=3, capacity=20),
        )
    )

    assert problem.total_capacity == 45


def test_total_capacity_is_zero_without_vehicles() -> None:
    problem = make_problem()

    assert problem.total_capacity == 0


def test_max_capacity_returns_largest_vehicle_capacity() -> None:
    problem = make_problem(
        vehicles=(
            Vehicle(id=1, capacity=10),
            Vehicle(id=2, capacity=20),
            Vehicle(id=3, capacity=15),
        )
    )

    assert problem.max_capacity == 20


def test_max_capacity_is_zero_without_vehicles() -> None:
    problem = make_problem()

    assert problem.max_capacity == 0
