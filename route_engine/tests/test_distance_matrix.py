import pytest

from route_engine.domain.models import Problem
from route_engine.examples.manual_distance_scenario import build_manual_scenario
from route_engine.services.distance_matrix import validate_distance_matrix
from route_engine.services.validator import ValidationError


def test_accepts_manual_scenario_matrix_without_mutating_it() -> None:
    problem, matrix = build_manual_scenario()
    original_matrix = [row.copy() for row in matrix]

    result = validate_distance_matrix(matrix, problem)

    assert isinstance(problem, Problem)
    assert result is matrix
    assert matrix == original_matrix


def test_rejects_incorrect_row_count() -> None:
    problem, matrix = build_manual_scenario()
    matrix.pop()

    with pytest.raises(ValidationError) as exc_info:
        validate_distance_matrix(matrix, problem)

    assert exc_info.value.errors[0]["field"] == "distance_matrix"


def test_rejects_incorrect_column_count() -> None:
    problem, matrix = build_manual_scenario()
    matrix[0].pop()

    with pytest.raises(ValidationError) as exc_info:
        validate_distance_matrix(matrix, problem)

    assert exc_info.value.errors[0]["field"] == "distance_matrix[0]"


def test_rejects_rows_with_different_lengths() -> None:
    problem, matrix = build_manual_scenario()
    matrix[2].append(500)

    with pytest.raises(ValidationError) as exc_info:
        validate_distance_matrix(matrix, problem)

    assert exc_info.value.errors[0]["field"] == "distance_matrix[2]"


def test_rejects_non_list_matrix() -> None:
    problem, matrix = build_manual_scenario()

    with pytest.raises(ValidationError) as exc_info:
        validate_distance_matrix(tuple(matrix), problem)

    assert exc_info.value.errors[0]["field"] == "distance_matrix"


def test_rejects_non_list_row() -> None:
    problem, matrix = build_manual_scenario()
    matrix[2] = tuple(matrix[2])

    with pytest.raises(ValidationError) as exc_info:
        validate_distance_matrix(matrix, problem)

    assert exc_info.value.errors[0]["field"] == "distance_matrix[2]"


@pytest.mark.parametrize("invalid_value", [-1, 1.5, "100", None, True])
def test_rejects_invalid_distance_values(invalid_value: object) -> None:
    problem, matrix = build_manual_scenario()
    matrix[1][2] = invalid_value

    with pytest.raises(ValidationError) as exc_info:
        validate_distance_matrix(matrix, problem)

    assert exc_info.value.errors[0]["field"] == "distance_matrix[1][2]"


def test_rejects_nonzero_diagonal() -> None:
    problem, matrix = build_manual_scenario()
    matrix[3][3] = 1

    with pytest.raises(ValidationError) as exc_info:
        validate_distance_matrix(matrix, problem)

    assert exc_info.value.errors[0] == {
        "field": "distance_matrix[3][3]",
        "message": "Diagonal da matriz deve ser zero",
    }


def test_accepts_asymmetric_matrix() -> None:
    problem, matrix = build_manual_scenario()
    matrix[0][1] = 900

    assert validate_distance_matrix(matrix, problem) is matrix


def test_accepts_zero_off_diagonal() -> None:
    problem, matrix = build_manual_scenario()
    matrix[1][2] = 0

    assert validate_distance_matrix(matrix, problem) is matrix


def test_matrix_indices_follow_delivery_order_not_delivery_ids() -> None:
    problem, matrix = build_manual_scenario()

    assert [delivery.id for delivery in problem.deliveries] == [101, 102, 103, 104]
    assert matrix[1][2] == 400  # A to B
    assert matrix[1][3] == 2000  # A to C
    assert matrix[3][4] == 400  # C to D


def test_manual_reference_routes_match_distance_and_capacity_totals() -> None:
    problem, matrix = build_manual_scenario()
    routes = {
        152: [0, 1, 2, 0],
        153: [0, 3, 4, 0],
    }
    vehicles_by_id = {vehicle.id: vehicle for vehicle in problem.vehicles}
    visited_delivery_indices = [
        point_index
        for route in routes.values()
        for point_index in route
        if point_index != 0
    ]

    assert sorted(visited_delivery_indices) == [1, 2, 3, 4]

    route_loads = {
        vehicle_id: sum(
            problem.deliveries[point_index - 1].demand
            for point_index in route
            if point_index != 0
        )
        for vehicle_id, route in routes.items()
    }
    route_distances = {
        vehicle_id: sum(
            matrix[start][end] for start, end in zip(route, route[1:], strict=False)
        )
        for vehicle_id, route in routes.items()
    }

    assert route_loads == {152: 8, 153: 6}
    assert all(
        route_loads[vehicle_id] <= vehicles_by_id[vehicle_id].capacity
        for vehicle_id in routes
    )
    assert route_distances == {152: 2600, 153: 2600}
    assert sum(route_distances.values()) == 5200
