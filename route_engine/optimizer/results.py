"""Structured output from the route solver."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class SolverStatus(StrEnum):
    SOLUTION_FOUND = "solution_found"
    INFEASIBLE = "infeasible"
    NO_SOLUTION = "search_ended_without_solution"
    INVALID_MODEL = "invalid_model"


@dataclass(frozen=True)
class RoutePoint:
    kind: Literal["depot", "delivery"]
    id: int
    matrix_index: int


@dataclass(frozen=True)
class VehicleRoute:
    vehicle_id: int
    points: tuple[RoutePoint, ...]
    load: int
    distance_meters: int


@dataclass(frozen=True)
class SolveResult:
    status: SolverStatus
    routes: tuple[VehicleRoute, ...] | None
    total_distance_meters: int | None
    ortools_status_code: int
