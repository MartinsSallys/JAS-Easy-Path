from collections import Counter

import pytest
from ortools.constraint_solver import routing_enums_pb2

from route_engine.domain.models import Problem
from route_engine.examples.manual_distance_scenario import build_manual_scenario
from route_engine.optimizer import SolverStatus, solve_routes
from route_engine.optimizer.ortools_solver import _status_without_solution
from route_engine.services.validator import ValidationError, validate_problem


def build_problem(vehicle_capacities: list[int], demands: list[int]) -> Problem:
    return validate_problem(
        {
            "depot": {
                "id": 0,
                "location": {"latitude": 0, "longitude": 0},
            },
            "vehicles": [
                {"id": 152 + index, "capacity": capacity}
                for index, capacity in enumerate(vehicle_capacities)
            ],
            "deliveries": [
                {
                    "id": 101 + index,
                    "demand": demand,
                    "location": {"latitude": index + 1, "longitude": index + 1},
                }
                for index, demand in enumerate(demands)
            ],
        }
    )


def test_solves_manual_scenario_and_reports_recalculated_routes() -> None:
    problem, matrix = build_manual_scenario()

    result = solve_routes(problem, matrix)

    assert result.status is SolverStatus.SOLUTION_FOUND
    assert result.routes is not None
    assert result.total_distance_meters == 5200
    routes_by_vehicle = {route.vehicle_id: route for route in result.routes}
    assert set(routes_by_vehicle) == {152, 153}

    delivery_by_id = {delivery.id: delivery for delivery in problem.deliveries}
    capacity_by_id = {vehicle.id: vehicle.capacity for vehicle in problem.vehicles}
    visited_delivery_ids = []
    recalculated_total_distance = 0

    for route in result.routes:
        assert route.points[0].kind == "depot"
        assert route.points[0].id == problem.depot.id
        assert route.points[-1].kind == "depot"
        assert route.points[-1].id == problem.depot.id

        route_delivery_ids = [
            point.id for point in route.points if point.kind == "delivery"
        ]
        visited_delivery_ids.extend(route_delivery_ids)
        recalculated_load = sum(
            delivery_by_id[delivery_id].demand for delivery_id in route_delivery_ids
        )
        recalculated_distance = sum(
            matrix[start.matrix_index][end.matrix_index]
            for start, end in zip(route.points, route.points[1:], strict=False)
        )

        assert route.load == recalculated_load
        assert route.load <= capacity_by_id[route.vehicle_id]
        assert route.distance_meters == recalculated_distance
        recalculated_total_distance += recalculated_distance

    assert Counter(visited_delivery_ids) == Counter({101: 1, 102: 1, 103: 1, 104: 1})
    assert recalculated_total_distance == result.total_distance_meters


def test_solves_problem_with_only_one_delivery() -> None:
    problem = build_problem(vehicle_capacities=[8, 6], demands=[4])
    matrix = [[0, 700], [700, 0]]

    result = solve_routes(problem, matrix)

    assert result.status is SolverStatus.SOLUTION_FOUND
    assert result.routes is not None
    assert result.total_distance_meters == 1400
    assert (
        sum(
            point.kind == "delivery"
            for route in result.routes
            for point in route.points
        )
        == 1
    )
    assert len(result.routes) == 2
    assert any(
        route.load == 0
        and route.distance_meters == 0
        and [point.kind for point in route.points] == ["depot", "depot"]
        for route in result.routes
    )


def test_reports_impossible_distribution_after_basic_checks_pass() -> None:
    problem = build_problem(vehicle_capacities=[8, 8], demands=[5, 5, 5])
    matrix = [[0] * 4 for _ in range(4)]

    assert problem.total_demand == 15
    assert problem.total_capacity == 16
    assert all(
        delivery.demand <= problem.max_capacity for delivery in problem.deliveries
    )

    result = solve_routes(problem, matrix)

    statuses = routing_enums_pb2.RoutingSearchStatus
    assert result.ortools_status_code in {
        statuses.ROUTING_FAIL,
        statuses.ROUTING_FAIL_TIMEOUT,
        statuses.ROUTING_INFEASIBLE,
    }
    expected_status = (
        SolverStatus.INFEASIBLE
        if result.ortools_status_code == statuses.ROUTING_INFEASIBLE
        else SolverStatus.NO_SOLUTION
    )
    assert result.status is expected_status
    assert result.routes is None
    assert result.total_distance_meters is None


@pytest.mark.parametrize(
    ("solver_code", "expected_status"),
    [
        (
            routing_enums_pb2.RoutingSearchStatus.ROUTING_INFEASIBLE,
            SolverStatus.INFEASIBLE,
        ),
        (
            routing_enums_pb2.RoutingSearchStatus.ROUTING_FAIL,
            SolverStatus.NO_SOLUTION,
        ),
        (
            routing_enums_pb2.RoutingSearchStatus.ROUTING_FAIL_TIMEOUT,
            SolverStatus.NO_SOLUTION,
        ),
        (
            routing_enums_pb2.RoutingSearchStatus.ROUTING_INVALID,
            SolverStatus.INVALID_MODEL,
        ),
    ],
)
def test_maps_solver_status_without_claiming_unproven_infeasibility(
    solver_code: int, expected_status: SolverStatus
) -> None:
    assert _status_without_solution(solver_code) is expected_status


def test_rejects_invalid_matrix_before_running_solver() -> None:
    problem, matrix = build_manual_scenario()
    matrix[0][0] = 100

    with pytest.raises(ValidationError) as exc_info:
        solve_routes(problem, matrix)

    assert exc_info.value.errors[0]["field"] == "distance_matrix[0][0]"


def test_rejects_nonpositive_search_limit() -> None:
    problem, matrix = build_manual_scenario()

    with pytest.raises(ValueError, match="inteiro positivo"):
        solve_routes(problem, matrix, time_limit_seconds=0)
