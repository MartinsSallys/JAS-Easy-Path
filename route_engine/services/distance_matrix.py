"""Validação manual de matrixz."""

from route_engine.domain.models import Problem
from route_engine.services.validator import ValidationError


def _raise_matrix_error(field: str, message: str) -> None:
    raise ValidationError([{"field": field, "message": message}])


def validate_distance_matrix(matrix: object, problem: Problem) -> list[list[int]]:
    """Validate an N x N matrix and return the same list without mutating it.

    N is one plus the number of deliveries in ``problem``. Index 0 is the
    depot; index i + 1 corresponds to ``problem.deliveries[i]``. IDs are not
    matrix indices.
    """
    if not isinstance(matrix, list):
        _raise_matrix_error(
            "distance_matrix", "Matriz de distâncias deve ser uma lista de listas"
        )

    expected_size = len(problem.deliveries) + 1
    if len(matrix) != expected_size:
        _raise_matrix_error(
            "distance_matrix",
            f"Matriz deve ter {expected_size} linhas",
        )

    for row_index, row in enumerate(matrix):
        row_field = f"distance_matrix[{row_index}]"
        if not isinstance(row, list):
            _raise_matrix_error(row_field, "Linha da matriz deve ser uma lista")
        if len(row) != expected_size:
            _raise_matrix_error(
                row_field,
                f"Linha deve ter {expected_size} colunas",
            )

        for column_index, value in enumerate(row):
            value_field = f"{row_field}[{column_index}]"
            if type(value) is not int:
                _raise_matrix_error(
                    value_field,
                    "Distância deve ser um número inteiro",
                )
            if value < 0:
                _raise_matrix_error(value_field, "Distância não pode ser negativa")
            if row_index == column_index and value != 0:
                _raise_matrix_error(value_field, "Diagonal da matriz deve ser zero")

    return matrix
