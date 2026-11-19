"""Reproducible manual scenario for checking distance-matrix handling."""

from route_engine.domain.models import Problem
from route_engine.services.validator import validate_problem


def build_manual_scenario() -> tuple[Problem, list[list[int]], list[list[int]]]:
    """Return a validated Problem and its hand-entered distance and time matrices.

    Coordinates are synthetic and valid. Matrix distances are manual values in
    meters, and durations are manual values in minutes. Neither matrix is
    calculated from those coordinates, and durations are not derived from
    distances.
    """
    problem = validate_problem(
        {
            "operating_hours": {"start": "08:00", "end": "18:00"},
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
    duration_matrix = [
        [0, 10, 12, 10, 12],
        [10, 0, 4, 20, 22],
        [12, 4, 0, 22, 24],
        [10, 20, 22, 0, 4],
        [12, 22, 24, 4, 0],
    ]
    return problem, distance_matrix, duration_matrix
