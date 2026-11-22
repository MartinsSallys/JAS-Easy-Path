"""Route Engine - Route optimization engine for JAS Easy Path."""

from route_engine.domain.constraints import DELIVERY_SERVICE_DURATION_MINUTES
from route_engine.domain.models import (
    Delivery,
    Depot,
    Location,
    Problem,
    TimeWindow,
    Vehicle,
)
from route_engine.optimizer import (
    RoutePoint,
    SolveResult,
    SolverStatus,
    VehicleRoute,
    solve_routes,
)
from route_engine.services.distance_matrix import validate_distance_matrix
from route_engine.services.duration_matrix import validate_duration_matrix
from route_engine.services.validator import (
    InfeasibleProblemError,
    ValidationError,
    validate_problem,
)

__all__ = [
    "DELIVERY_SERVICE_DURATION_MINUTES",
    "Delivery",
    "Depot",
    "InfeasibleProblemError",
    "Location",
    "Problem",
    "RoutePoint",
    "SolveResult",
    "SolverStatus",
    "TimeWindow",
    "ValidationError",
    "Vehicle",
    "VehicleRoute",
    "solve_routes",
    "validate_distance_matrix",
    "validate_duration_matrix",
    "validate_problem",
]

__version__ = "0.1.0"
