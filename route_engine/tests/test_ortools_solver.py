from collections import Counter

import pytest
from ortools.constraint_solver import routing_enums_pb2
from route_engine.domain.constraints import DELIVERY_SERVICE_DURATION_MINUTES
from route_engine.domain.models import Problem
from route_engine.examples.manual_distance_scenario import build_manual_scenario
from route_engine.optimizer import SolverStatus, solve_routes
from route_engine.optimizer.ortools_solver import _status_without_solution
from route_engine.services.validator import ValidationError, validate_problem


def build_problem(
    vehicle_capacities: list[int],
    demands: list[int],
    *,
    operating_hours: tuple[str, str] = ("08:00", "18:00"),
    time_windows: list[tuple[str, str] | None] | None = None,
) -> Problem:
    deliveries = []
    for index, demand in enumerate(demands):
        delivery = {
            "id": 101 + index,
            "demand": demand,
            "location": {"latitude": index + 1, "longitude": index + 1},
        }
        if time_windows is not None and time_windows[index] is not None:
            start, end = time_windows[index]
            delivery["time_window"] = {"start": start, "end": end}
        deliveries.append(delivery)

    return validate_problem(
        {
            "operating_hours": {
                "start": operating_hours[0],
                "end": operating_hours[1],
            },
            "depot": {
                "id": 0,
                "location": {"latitude": 0, "longitude": 0},
            },
            "vehicles": [
                {"id": 152 + index, "capacity": capacity}
                for index, capacity in enumerate(vehicle_capacities)
            ],
            "deliveries": deliveries,
        }
    )


def zero_duration_matrix(problem: Problem) -> list[list[int]]:
    size = len(problem.deliveries) + 1
    return [[0] * size for _ in range(size)]


def assert_solution_schedule(
    problem: Problem,
    result,
    distance_matrix: list[list[int]],
    duration_matrix: list[list[int]],
) -> None:
    assert result.status is SolverStatus.SOLUTION_FOUND
    assert result.routes is not None

    capacity_by_vehicle_id = {
        vehicle.id: vehicle.capacity for vehicle in problem.vehicles
    }
    delivery_by_matrix_index = {
        matrix_index: delivery
        for matrix_index, delivery in enumerate(problem.deliveries, start=1)
    }
    visited_delivery_indices = []
    total_distance = 0

    for route in result.routes:
        assert route.points[0].kind == "depot"
        assert route.points[0].id == problem.depot.id
        assert route.points[-1].kind == "depot"
        assert route.points[-1].id == problem.depot.id
        assert route.points[0].service_start_minute is None
        assert route.points[0].service_end_minute is None
        assert route.points[-1].service_start_minute is None
        assert route.points[-1].service_end_minute is None
        assert problem.operating_hours.start_minute <= route.departure_minute
        assert route.departure_minute <= problem.operating_hours.end_minute
        assert problem.operating_hours.start_minute <= route.return_minute
        assert route.return_minute <= problem.operating_hours.end_minute

        recalculated_load = 0
        recalculated_distance = 0
        previous_point = route.points[0]
        previous_finish = route.departure_minute
        for point_index, point in enumerate(route.points[1:], start=1):
            recalculated_distance += distance_matrix[previous_point.matrix_index][
                point.matrix_index
            ]
            earliest_possible_time = (
                previous_finish
                + duration_matrix[previous_point.matrix_index][point.matrix_index]
            )

            if point.kind == "delivery":
                delivery = delivery_by_matrix_index[point.matrix_index]
                assert point.id == delivery.id
                assert point.service_start_minute is not None
                assert point.service_end_minute is not None
                assert (
                    point.service_end_minute
                    == point.service_start_minute + DELIVERY_SERVICE_DURATION_MINUTES
                )
                assert point.service_start_minute >= earliest_possible_time
                assert point.service_start_minute >= delivery.time_window.start_minute
                assert point.service_end_minute <= delivery.time_window.end_minute
                recalculated_load += delivery.demand
                visited_delivery_indices.append(point.matrix_index)
                previous_finish = point.service_end_minute
            else:
                assert point_index == len(route.points) - 1
                assert route.return_minute >= earliest_possible_time
                previous_finish = route.return_minute

            previous_point = point

        assert route.load == recalculated_load
        assert route.load <= capacity_by_vehicle_id[route.vehicle_id]
        assert route.distance_meters == recalculated_distance
        total_distance += recalculated_distance

    assert Counter(visited_delivery_indices) == Counter(
        range(1, len(problem.deliveries) + 1)
    )
    assert result.total_distance_meters == total_distance


def assert_no_solution_without_overclaiming(result) -> None:
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


def test_solves_manual_scenario_and_reports_recalculated_routes() -> None:
    problem, distance_matrix, duration_matrix = build_manual_scenario()

    result = solve_routes(problem, distance_matrix, duration_matrix)

    assert result.total_distance_meters == 5200
    assert {route.vehicle_id for route in result.routes or ()} == {152, 153}
    assert_solution_schedule(problem, result, distance_matrix, duration_matrix)


def test_solves_problem_with_only_one_delivery_and_an_unused_vehicle() -> None:
    problem = build_problem(vehicle_capacities=[8, 6], demands=[4])
    distance_matrix = [[0, 700], [700, 0]]
    duration_matrix = zero_duration_matrix(problem)

    result = solve_routes(problem, distance_matrix, duration_matrix)

    assert result.total_distance_meters == 1400
    assert_solution_schedule(problem, result, distance_matrix, duration_matrix)
    assert any(
        route.load == 0
        and route.distance_meters == 0
        and [point.kind for point in route.points] == ["depot", "depot"]
        for route in result.routes or ()
    )


def test_reports_impossible_capacity_distribution_without_overclaiming() -> None:
    problem = build_problem(vehicle_capacities=[8, 8], demands=[5, 5, 5])
    distance_matrix = [[0] * 4 for _ in range(4)]

    assert problem.total_demand == 15
    assert problem.total_capacity == 16
    assert all(
        delivery.demand <= problem.max_capacity for delivery in problem.deliveries
    )

    result = solve_routes(
        problem,
        distance_matrix,
        zero_duration_matrix(problem),
    )

    assert_no_solution_without_overclaiming(result)


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


def test_rejects_invalid_distance_matrix_before_running_solver() -> None:
    problem, distance_matrix, duration_matrix = build_manual_scenario()
    distance_matrix[0][0] = 100

    with pytest.raises(ValidationError) as exc_info:
        solve_routes(problem, distance_matrix, duration_matrix)

    assert exc_info.value.errors[0]["field"] == "distance_matrix[0][0]"


def test_rejects_invalid_duration_matrix_before_running_solver() -> None:
    problem, distance_matrix, duration_matrix = build_manual_scenario()
    duration_matrix[0][1] = True

    with pytest.raises(ValidationError) as exc_info:
        solve_routes(problem, distance_matrix, duration_matrix)

    assert exc_info.value.errors[0]["field"] == "duration_matrix[0][1]"


def test_rejects_nonpositive_search_limit() -> None:
    problem, distance_matrix, duration_matrix = build_manual_scenario()

    with pytest.raises(ValueError, match="inteiro positivo"):
        solve_routes(
            problem,
            distance_matrix,
            duration_matrix,
            time_limit_seconds=0,
        )


def test_allows_early_arrival_and_reports_waiting_before_service() -> None:
    problem = build_problem(
        [10],
        [1],
        operating_hours=("08:00", "10:00"),
        time_windows=[("09:00", "09:30")],
    )
    distance_matrix = [[0, 100], [100, 0]]
    duration_matrix = [[0, 10], [10, 0]]

    result = solve_routes(problem, distance_matrix, duration_matrix)

    assert_solution_schedule(problem, result, distance_matrix, duration_matrix)
    route = result.routes[0]
    delivery_point = next(point for point in route.points if point.kind == "delivery")
    arrival_minute = route.departure_minute + duration_matrix[0][1]
    assert route.departure_minute == problem.operating_hours.start_minute
    assert delivery_point.service_start_minute == 9 * 60
    assert delivery_point.service_start_minute > arrival_minute


def test_allows_service_to_finish_exactly_at_window_close() -> None:
    problem = build_problem(
        [10],
        [1],
        operating_hours=("08:00", "11:00"),
        time_windows=[("09:52", "10:00")],
    )
    distance_matrix = [[0, 100], [100, 0]]
    duration_matrix = [[0, 112], [5, 0]]

    result = solve_routes(problem, distance_matrix, duration_matrix)

    assert_solution_schedule(problem, result, distance_matrix, duration_matrix)
    delivery_point = next(
        point for point in result.routes[0].points if point.kind == "delivery"
    )
    assert delivery_point.service_end_minute == 10 * 60


def test_accepts_effective_window_of_exactly_eight_minutes() -> None:
    problem = build_problem(
        [10],
        [1],
        operating_hours=("08:00", "09:00"),
        time_windows=[("08:00", "08:08")],
    )
    distance_matrix = [[0, 100], [100, 0]]
    duration_matrix = [[0, 0], [0, 0]]

    result = solve_routes(problem, distance_matrix, duration_matrix)

    assert_solution_schedule(problem, result, distance_matrix, duration_matrix)
    delivery_point = next(
        point for point in result.routes[0].points if point.kind == "delivery"
    )
    assert delivery_point.service_end_minute == 8 * 60 + 8


def test_rejects_arrival_inside_window_when_service_would_finish_too_late() -> None:
    problem = build_problem(
        [10],
        [1],
        operating_hours=("08:50", "10:00"),
        time_windows=[("09:00", "09:10")],
    )
    distance_matrix = [[0, 100], [100, 0]]
    duration_matrix = [[0, 15], [1, 0]]

    result = solve_routes(problem, distance_matrix, duration_matrix)

    assert_no_solution_without_overclaiming(result)


def test_rejects_route_when_return_exceeds_operating_hours() -> None:
    problem = build_problem(
        [10],
        [1],
        operating_hours=("08:00", "09:00"),
        time_windows=[("08:10", "08:30")],
    )
    distance_matrix = [[0, 100], [100, 0]]
    duration_matrix = [[0, 10], [50, 0]]

    result = solve_routes(problem, distance_matrix, duration_matrix)

    assert_no_solution_without_overclaiming(result)


def test_reports_temporal_impossibility_when_capacity_is_sufficient() -> None:
    problem = build_problem(
        [2],
        [1, 1],
        operating_hours=("08:00", "10:00"),
        time_windows=[("08:00", "08:08"), ("08:09", "08:17")],
    )
    distance_matrix = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    duration_matrix = [[0, 0, 0], [0, 0, 10], [0, 10, 0]]

    assert problem.total_demand == 2
    assert problem.total_capacity == 2
    result = solve_routes(problem, distance_matrix, duration_matrix)

    assert_no_solution_without_overclaiming(result)


def test_delivery_windows_change_lowest_distance_feasible_route_order() -> None:
    operating_hours = ("08:00", "10:00")
    wide_window_problem = build_problem(
        vehicle_capacities=[2],
        demands=[1, 1],
        operating_hours=operating_hours,
    )
    restricted_window_problem = build_problem(
        vehicle_capacities=[2],
        demands=[1, 1],
        operating_hours=operating_hours,
        time_windows=[None, ("08:05", "08:13")],
    )
    distance_matrix = [
        [0, 100, 500],
        [500, 0, 100],
        [100, 500, 0],
    ]
    duration_matrix = [
        [0, 5, 5],
        [5, 0, 5],
        [5, 5, 0],
    ]

    wide_window_result = solve_routes(
        wide_window_problem,
        distance_matrix,
        duration_matrix,
    )
    restricted_window_result = solve_routes(
        restricted_window_problem,
        distance_matrix,
        duration_matrix,
    )

    assert_solution_schedule(
        wide_window_problem,
        wide_window_result,
        distance_matrix,
        duration_matrix,
    )
    assert_solution_schedule(
        restricted_window_problem,
        restricted_window_result,
        distance_matrix,
        duration_matrix,
    )
    assert wide_window_result.total_distance_meters == 300
    assert restricted_window_result.total_distance_meters == 1500

    wide_window_route = wide_window_result.routes[0]
    restricted_window_route = restricted_window_result.routes[0]
    wide_sequence = [
        point.id for point in wide_window_route.points if point.kind == "delivery"
    ]
    restricted_sequence = [
        point.id for point in restricted_window_route.points if point.kind == "delivery"
    ]
    assert wide_sequence == [101, 102]
    assert restricted_sequence == [102, 101]
    assert wide_sequence != restricted_sequence

    restricted_delivery_b = next(
        point
        for point in restricted_window_route.points
        if point.kind == "delivery" and point.id == 102
    )
    assert restricted_delivery_b.service_start_minute == 8 * 60 + 5
    assert restricted_delivery_b.service_end_minute == 8 * 60 + 13
