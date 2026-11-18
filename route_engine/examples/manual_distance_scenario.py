"""Reproducible manual scenario for checking distance-matrix handling."""

from route_engine.domain.models import Problem
from route_engine.services.validator import validate_problem


def build_manual_scenario() -> tuple[Problem, list[list[int]]]:
    """Return a validated Problem and its hand-entered distance matrix.

    Coordinates are synthetic and valid. Matrix distances are manual values in
    meters; they are not calculated from those coordinates.
    """
    problem = validate_problem(
        {
            "depot": {
                "id": 0,
                "location": {"latitude": -2.9, "longitude": -41.7},
            },
            "vehicles": [
                {"id": 152, "capacity": 8},
                {"id": 153, "capacity": 6},
            ],
            "deliveries": [
                {
                    "id": 101,
                    "demand": 4,
                    "location": {"latitude": -2.91, "longitude": -41.71},
                },
                {
                    "id": 102,
                    "demand": 4,
                    "location": {"latitude": -2.92, "longitude": -41.72},
                },
                {
                    "id": 103,
                    "demand": 3,
                    "location": {"latitude": -2.93, "longitude": -41.73},
                },
                {
                    "id": 104,
                    "demand": 3,
                    "location": {"latitude": -2.94, "longitude": -41.74},
                },
            ],
        }
    )
    distance_matrix = [
        [0, 1000, 1200, 1000, 1200],
        [1000, 0, 400, 2000, 2200],
        [1200, 400, 0, 2200, 2400],
        [1000, 2000, 2200, 0, 400],
        [1200, 2200, 2400, 400, 0],
    ]
    return problem, distance_matrix
