import pytest

from route_engine.examples.manual_distance_scenario import build_manual_scenario
from route_engine.services.duration_matrix import validate_duration_matrix
from route_engine.services.validator import ValidationError


def test_accepts_manual_duration_matrix_without_mutating_it() -> None:
    problem, _, matrix = build_manual_scenario()
    original_matrix = [row.copy() for row in matrix]

    result = validate_duration_matrix(matrix, problem)

    assert result is matrix
    assert matrix == original_matrix
    assert matrix == [
        [0, 10, 12, 10, 12],
        [10, 0, 4, 20, 22],
        [12, 4, 0, 22, 24],
        [10, 20, 22, 0, 4],
        [12, 22, 24, 4, 0],
    ]


def test_rejects_incorrect_row_count() -> None:
    problem, _, matrix = build_manual_scenario()
    matrix.pop()

    with pytest.raises(ValidationError) as exc_info:
        validate_duration_matrix(matrix, problem)

    assert exc_info.value.errors[0]["field"] == "duration_matrix"


def test_rejects_incorrect_column_count() -> None:
    problem, _, matrix = build_manual_scenario()
    matrix[0].pop()

    with pytest.raises(ValidationError) as exc_info:
        validate_duration_matrix(matrix, problem)

    assert exc_info.value.errors[0]["field"] == "duration_matrix[0]"


@pytest.mark.parametrize("matrix", [(), "matrix", None])
def test_rejects_non_list_matrix(matrix: object) -> None:
    problem, _, _ = build_manual_scenario()

    with pytest.raises(ValidationError) as exc_info:
        validate_duration_matrix(matrix, problem)

    assert exc_info.value.errors[0]["field"] == "duration_matrix"


def test_rejects_non_list_row() -> None:
    problem, _, matrix = build_manual_scenario()
    matrix[2] = tuple(matrix[2])

    with pytest.raises(ValidationError) as exc_info:
        validate_duration_matrix(matrix, problem)

    assert exc_info.value.errors[0]["field"] == "duration_matrix[2]"


@pytest.mark.parametrize("invalid_value", [-1, 1.5, "10", None, True])
def test_rejects_invalid_duration_values(invalid_value: object) -> None:
    problem, _, matrix = build_manual_scenario()
    matrix[1][2] = invalid_value

    with pytest.raises(ValidationError) as exc_info:
        validate_duration_matrix(matrix, problem)

    assert exc_info.value.errors[0]["field"] == "duration_matrix[1][2]"


def test_rejects_nonzero_diagonal() -> None:
    problem, _, matrix = build_manual_scenario()
    matrix[3][3] = 1

    with pytest.raises(ValidationError) as exc_info:
        validate_duration_matrix(matrix, problem)

    assert exc_info.value.errors[0] == {
        "field": "duration_matrix[3][3]",
        "message": "Diagonal da matriz deve ser zero",
    }


def test_accepts_asymmetric_and_zero_off_diagonal_durations() -> None:
    problem, _, matrix = build_manual_scenario()
    matrix[0][1] = 0
    matrix[1][0] = 7
    matrix[2][3] = 0

    assert validate_duration_matrix(matrix, problem) is matrix
