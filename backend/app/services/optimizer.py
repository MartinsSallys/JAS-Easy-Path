import math
import time as time_module
from typing import Protocol

from ortools.constraint_solver import routing_enums_pb2
from route_engine import (
    InfeasibleProblemError,
    SolveResult,
    SolverStatus,
    ValidationError,
    VehicleRoute,
    solve_routes,
    validate_problem,
)

from app.core.config import settings
from app.schemas import (
    OptimizationLocation,
    OptimizationRequest,
    OptimizationResponse,
    RouteResult,
    StopResult,
)

OPERATING_HOURS = {"start": "08:00", "end": "18:00"}
"""Expediente fixo do MVP (limitação conhecida, ver docs/arquitetura-mvp.md)."""

AVERAGE_SPEED_M_PER_MIN = 500.0
"""Velocidade média assumida (~30 km/h) para derivar duração da distância."""

METERS_PER_KM = 1000

MIN_ROUTE_POINTS = 3
"""Depósito na saída + ao menos uma entrega + depósito no retorno."""


def _haversine_m(origin: OptimizationLocation, destination: OptimizationLocation) -> float:
    earth_radius_m = 6_371_000.0
    lat1 = math.radians(origin.latitude)
    lon1 = math.radians(origin.longitude)
    lat2 = math.radians(destination.latitude)
    lon2 = math.radians(destination.longitude)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return earth_radius_m * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _minutes_to_hhmm(minute: int | None) -> str | None:
    if minute is None:
        return None
    return f"{(minute // 60) % 24:02d}:{minute % 60:02d}"


class MatrixProvider(Protocol):
    """Fonte das matrizes de custo exigidas pelo motor.

    Recebe as localizações na ordem ``[depot, *deliveries]`` e retorna
    ``(distancia_metros, duracao_minutos)``, ambas N x N de inteiros.
    """

    def build(
        self, locations: list[OptimizationLocation]
    ) -> tuple[list[list[int]], list[list[int]]]: ...


class HaversineMatrixProvider:
    """Matrizes por distância em linha reta; duração derivada da distância.

    Determinístico e sem dependência externa. Pode ser substituído por um
    provedor baseado em serviço de rotas (ex.: OpenRouteService) sem alterar
    o adapter nem o endpoint.
    """

    def build(
        self, locations: list[OptimizationLocation]
    ) -> tuple[list[list[int]], list[list[int]]]:
        size = len(locations)
        distances = [[0] * size for _ in range(size)]
        durations = [[0] * size for _ in range(size)]
        for i, origin in enumerate(locations):
            for j, destination in enumerate(locations):
                if i == j:
                    continue
                meters = _haversine_m(origin, destination)
                distances[i][j] = int(meters)
                durations[i][j] = max(1, round(meters / AVERAGE_SPEED_M_PER_MIN))
        return distances, durations


class RouteEngineAdapter:
    """Adapta o contrato da API para o motor ``validate_problem``/``solve_routes``.

    O motor aplica capacidade, expediente (fixo 08:00–18:00 no MVP) e janelas
    de entrega com 8 minutos de atendimento concluído dentro da janela.
    Não há atribuição parcial: ou todas as entregas são atendidas ou a
    resposta é um status de falha — ``unassigned`` só aparece nesses casos.

    Status possíveis: ``feasible`` (solução), ``invalid_input`` (dados
    malformados), ``infeasible`` (inviabilidade comprovada na validação ou
    pelo solver), ``no_solution`` (busca encerrada sem solução), ``timeout``
    (busca encerrada pelo limite de tempo) e ``invalid_model`` (modelo ou
    matriz rejeitados pelo solver).
    """

    def __init__(
        self,
        matrix_provider: MatrixProvider | None = None,
        time_limit_seconds: int | None = None,
    ) -> None:
        self.matrix_provider = matrix_provider or HaversineMatrixProvider()
        self.time_limit_seconds = (
            time_limit_seconds or settings.ortools_time_limit_seconds
        )

    def solve(self, request: OptimizationRequest) -> OptimizationResponse:
        started = time_module.monotonic()
        try:
            problem = validate_problem(self._raw_problem(request))
        except InfeasibleProblemError as exc:
            return self._failed(request, started, "infeasible", exc)
        except ValidationError as exc:
            return self._failed(request, started, "invalid_input", exc)

        locations = [request.depot, *(d.location for d in request.deliveries)]
        distance_m, duration_min = self.matrix_provider.build(locations)

        time_limit = self.time_limit_seconds
        if request.options is not None:
            time_limit = request.options.time_limit_seconds

        try:
            result = solve_routes(
                problem,
                distance_m,
                duration_min,
                time_limit_seconds=time_limit,
            )
        except ValidationError as exc:
            return self._failed(request, started, "invalid_model", exc)

        return self._from_result(result, request, started)

    def _raw_problem(self, request: OptimizationRequest) -> dict:
        deliveries = []
        for delivery in request.deliveries:
            raw = {
                "id": delivery.id,
                "demand": delivery.demand,
                "location": {
                    "latitude": delivery.location.latitude,
                    "longitude": delivery.location.longitude,
                    "address": delivery.location.address,
                },
            }
            if delivery.time_window_start and delivery.time_window_end:
                raw["time_window"] = {
                    "start": delivery.time_window_start,
                    "end": delivery.time_window_end,
                }
            deliveries.append(raw)

        return {
            "operating_hours": OPERATING_HOURS,
            "depot": {
                "id": 0,
                "location": {
                    "latitude": request.depot.latitude,
                    "longitude": request.depot.longitude,
                    "address": request.depot.address,
                },
            },
            "vehicles": [
                {"id": vehicle.id, "capacity": vehicle.capacity}
                for vehicle in request.vehicles
            ],
            "deliveries": deliveries,
        }

    def _failed(
        self,
        request: OptimizationRequest,
        started: float,
        status: str,
        exc: ValidationError | None = None,
    ) -> OptimizationResponse:
        message = exc.errors[0]["message"] if exc is not None and exc.errors else None
        return OptimizationResponse(
            routes=[],
            unassigned=list(request.deliveries),
            status=status,
            solve_time_ms=self._elapsed_ms(started),
            message=message,
        )

    @staticmethod
    def _failure_status(result: SolveResult) -> str:
        if result.status is SolverStatus.INFEASIBLE:
            return "infeasible"
        if result.status is SolverStatus.INVALID_MODEL:
            return "invalid_model"
        if (
            result.ortools_status_code
            == routing_enums_pb2.RoutingSearchStatus.ROUTING_FAIL_TIMEOUT
        ):
            return "timeout"
        return "no_solution"

    def _from_result(
        self,
        result: SolveResult,
        request: OptimizationRequest,
        started: float,
    ) -> OptimizationResponse:
        if result.status is not SolverStatus.SOLUTION_FOUND or not result.routes:
            return self._failed(request, started, self._failure_status(result))

        routes = [
            self._from_route(route, request)
            for route in result.routes
            if len(route.points) >= MIN_ROUTE_POINTS
        ]
        return OptimizationResponse(
            routes=routes,
            unassigned=[],
            status="feasible",
            solve_time_ms=self._elapsed_ms(started),
        )

    def _from_route(
        self, route: VehicleRoute, request: OptimizationRequest
    ) -> RouteResult:
        deliveries_by_id = {d.id: d for d in request.deliveries}
        stops: list[StopResult] = []
        load = 0
        for sequence, point in enumerate(route.points):
            if point.kind == "depot":
                is_return = sequence == len(route.points) - 1
                minute = (
                    route.return_minute if is_return else route.departure_minute
                )
                stops.append(
                    StopResult(
                        delivery_id=None,
                        location=request.depot,
                        sequence=sequence,
                        arrival_time=_minutes_to_hhmm(minute),
                        departure_time=_minutes_to_hhmm(minute),
                        load_after=0 if is_return else load,
                    )
                )
            else:
                delivery = deliveries_by_id[point.id]
                load += delivery.demand
                stops.append(
                    StopResult(
                        delivery_id=point.id,
                        location=delivery.location,
                        sequence=sequence,
                        arrival_time=_minutes_to_hhmm(point.service_start_minute),
                        departure_time=_minutes_to_hhmm(point.service_end_minute),
                        load_after=load,
                    )
                )

        return RouteResult(
            vehicle_id=route.vehicle_id,
            stops=stops,
            total_distance_km=round(route.distance_meters / METERS_PER_KM, 2),
            total_duration_min=route.return_minute - route.departure_minute,
            total_load=load,
        )

    def _elapsed_ms(self, started: float) -> int:
        return int((time_module.monotonic() - started) * 1000)


_optimizer_holder: dict = {"instance": None}


def get_optimizer() -> RouteEngineAdapter:
    if _optimizer_holder["instance"] is None:
        _optimizer_holder["instance"] = RouteEngineAdapter()
    return _optimizer_holder["instance"]


def reset_optimizer() -> None:
    _optimizer_holder["instance"] = None
