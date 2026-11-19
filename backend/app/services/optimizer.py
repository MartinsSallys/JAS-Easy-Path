import contextlib
from datetime import time

from app.core.config import settings
from app.schemas import (
    OptimizationDelivery,
    OptimizationLocation,
    OptimizationRequest,
    OptimizationResponse,
    OptimizationVehicle,
    RouteResult,
    StopResult,
)

try:
    from route_engine import (
        Delivery,
        Depot,
        Location,
        Problem,
        Route,
        RouteEngine,
        Solution,
        SolveStatus,
        Stop,
        Vehicle,
        time_to_minutes,
    )
except ImportError:
    Depot = None
    Delivery = None
    Location = None
    Problem = None
    RouteEngine = None
    Solution = None
    SolveStatus = None
    Stop = None
    Vehicle = None
    time_to_minutes = None
    Route = None


class RouteEngineAdapter:
    def __init__(self) -> None:
        if RouteEngine is None:
            raise RuntimeError("route_engine not available. Install route_engine package.")
        self.engine = RouteEngine(
            time_limit_seconds=settings.ortools_time_limit_seconds,
            first_solution_strategy=settings.ortools_first_solution_strategy,
        )

    def _to_engine_location(self, loc: OptimizationLocation) -> Location:
        return Location(
            latitude=loc.latitude,
            longitude=loc.longitude,
            address=loc.address,
        )

    def _to_engine_depot(self, depot: OptimizationLocation) -> Depot:
        return Depot(id=0, location=self._to_engine_location(depot))

    def _to_engine_vehicle(self, v: OptimizationVehicle) -> Vehicle:
        return Vehicle(id=v.id, capacity=v.capacity)

    def _to_engine_delivery(self, d: OptimizationDelivery) -> Delivery:
        tw_start = None
        tw_end = None
        if d.time_window_start:
            with contextlib.suppress(ValueError):
                tw_start = time.fromisoformat(d.time_window_start)
        if d.time_window_end:
            with contextlib.suppress(ValueError):
                tw_end = time.fromisoformat(d.time_window_end)
        return Delivery(
            id=d.id,
            demand=d.demand,
            location=self._to_engine_location(d.location),
            time_window_start=tw_start,
            time_window_end=tw_end,
            service_time_min=8,
        )

    def _to_engine_problem(self, request: OptimizationRequest) -> Problem:
        work_start = time(8, 0)
        work_end = time(18, 0)
        if request.options and request.options.time_limit_seconds:
            pass
        return Problem(
            depot=self._to_engine_depot(request.depot),
            vehicles=tuple(self._to_engine_vehicle(v) for v in request.vehicles),
            deliveries=tuple(self._to_engine_delivery(d) for d in request.deliveries),
            work_start=work_start,
            work_end=work_end,
        )

    def _from_engine_stop(self, stop: Stop, depot_loc: OptimizationLocation) -> StopResult:
        return StopResult(
            delivery_id=stop.delivery_id,
            location=OptimizationLocation(
                latitude=stop.location.latitude,
                longitude=stop.location.longitude,
                address=stop.location.address,
            ),
            sequence=stop.sequence,
            arrival_time=stop.arrival_time.isoformat() if stop.arrival_time else None,
            departure_time=stop.departure_time.isoformat() if stop.departure_time else None,
            load_after=stop.load_after,
        )

    def _from_engine_route(
        self, route: Route, depot_loc: OptimizationLocation
    ) -> RouteResult:
        return RouteResult(
            vehicle_id=route.vehicle_id,
            stops=[self._from_engine_stop(s, depot_loc) for s in route.stops],
            total_distance_km=round(route.total_distance_m / 1000, 2),
            total_duration_min=route.total_duration_min,
            total_load=route.total_load,
        )

    def _from_engine_solution(
        self, solution: Solution, request: OptimizationRequest
    ) -> OptimizationResponse:
        unassigned = [
            OptimizationDelivery(
                id=d.id,
                demand=d.demand,
                location=OptimizationLocation(
                    latitude=d.location.latitude,
                    longitude=d.location.longitude,
                    address=d.location.address,
                ),
                time_window_start=(
                    d.time_window_start.isoformat() if d.time_window_start else None
                ),
                time_window_end=(
                    d.time_window_end.isoformat() if d.time_window_end else None
                ),
            )
            for d in solution.unassigned
        ]

        status_map = {
            SolveStatus.OPTIMAL: "optimal",
            SolveStatus.FEASIBLE: "feasible",
            SolveStatus.INFEASIBLE: "infeasible",
            SolveStatus.TIMEOUT: "timeout",
        }

        return OptimizationResponse(
            routes=[self._from_engine_route(r, request.depot) for r in solution.routes],
            unassigned=unassigned,
            status=status_map.get(solution.status, "unknown"),
            solve_time_ms=solution.solve_time_ms,
        )

    def solve(self, request: OptimizationRequest) -> OptimizationResponse:
        problem = self._to_engine_problem(request)
        solution = self.engine.solve(problem)
        return self._from_engine_solution(solution, request)


_optimizer_holder: dict = {"instance": None}


def get_optimizer() -> RouteEngineAdapter:
    if _optimizer_holder["instance"] is None:
        _optimizer_holder["instance"] = RouteEngineAdapter()
    return _optimizer_holder["instance"]


def reset_optimizer() -> None:
    _optimizer_holder["instance"] = None