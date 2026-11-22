"""Capacitated vehicle routing integration using Google OR-Tools."""

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from route_engine.domain.constraints import DELIVERY_SERVICE_DURATION_MINUTES
from route_engine.domain.models import Problem
from route_engine.optimizer.results import (
    RoutePoint,
    SolveResult,
    SolverStatus,
    VehicleRoute,
)
from route_engine.services.distance_matrix import validate_distance_matrix
from route_engine.services.duration_matrix import validate_duration_matrix


def _status_without_solution(status_code: int) -> SolverStatus:
    statuses = routing_enums_pb2.RoutingSearchStatus
    if status_code == statuses.ROUTING_INFEASIBLE:
        return SolverStatus.INFEASIBLE
    if status_code == statuses.ROUTING_INVALID:
        return SolverStatus.INVALID_MODEL
    return SolverStatus.NO_SOLUTION


def _point_for_index(
    problem: Problem,
    matrix_index: int,
    service_start_minute: int | None = None,
) -> RoutePoint:
    if matrix_index == 0:
        return RoutePoint(kind="depot", id=problem.depot.id, matrix_index=0)

    delivery = problem.deliveries[matrix_index - 1]
    if service_start_minute is None:
        raise RuntimeError("Faltou horário de atendimento para uma entrega")
    return RoutePoint(
        kind="delivery",
        id=delivery.id,
        matrix_index=matrix_index,
        service_start_minute=service_start_minute,
        service_end_minute=service_start_minute + DELIVERY_SERVICE_DURATION_MINUTES,
    )


def _extract_routes(
    problem: Problem,
    distance_matrix: list[list[int]],
    duration_matrix: list[list[int]],
    manager: pywrapcp.RoutingIndexManager,
    routing: pywrapcp.RoutingModel,
    solution: pywrapcp.Assignment,
) -> tuple[VehicleRoute, ...]:
    routes = []
    for vehicle_index, vehicle in enumerate(problem.vehicles):
        points = []
        load = 0
        distance_meters = 0
        departure_minute = problem.operating_hours.start_minute
        previous_finish = departure_minute
        previous_matrix_index = 0
        routing_index = routing.Start(vehicle_index)

        while True:
            matrix_index = manager.IndexToNode(routing_index)
            if routing.IsEnd(routing_index):
                points.append(_point_for_index(problem, matrix_index))
                return_minute = (
                    previous_finish
                    + duration_matrix[previous_matrix_index][matrix_index]
                )
                break

            if matrix_index == 0:
                points.append(_point_for_index(problem, matrix_index))
            else:
                delivery = problem.deliveries[matrix_index - 1]
                arrival_minute = (
                    previous_finish
                    + duration_matrix[previous_matrix_index][matrix_index]
                )
                service_start_minute = max(
                    arrival_minute,
                    delivery.time_window.start_minute,
                )
                service_end_minute = (
                    service_start_minute + DELIVERY_SERVICE_DURATION_MINUTES
                )
                if service_end_minute > delivery.time_window.end_minute:
                    raise RuntimeError(
                        "A rota encontrada não admite uma programação concreta"
                    )
                points.append(
                    _point_for_index(problem, matrix_index, service_start_minute)
                )
                previous_finish = service_end_minute

            next_routing_index = solution.Value(routing.NextVar(routing_index))
            next_matrix_index = manager.IndexToNode(next_routing_index)
            distance_meters += distance_matrix[matrix_index][next_matrix_index]
            if matrix_index != 0:
                load += problem.deliveries[matrix_index - 1].demand
            previous_matrix_index = matrix_index
            routing_index = next_routing_index

        routes.append(
            VehicleRoute(
                vehicle_id=vehicle.id,
                points=tuple(points),
                load=load,
                distance_meters=distance_meters,
                departure_minute=departure_minute,
                return_minute=return_minute,
            )
        )

    return tuple(routes)


def solve_routes(
    problem: Problem,
    distance_matrix: object,
    duration_matrix: object,
    *,
    time_limit_seconds: int = 1,
) -> SolveResult:
    """Solve a distance-minimizing CVRP with operating hours and delivery windows.

    Both matrices use positions ``[depot, *problem.deliveries]``. The distance
    matrix is in meters and remains the only optimization objective; the
    duration matrix is in integer minutes and supplies temporal constraints.
    Delivery cumul values represent service starts. The returned schedule is
    reconstructed from the operating-day opening, waiting before service when
    needed; this does not add a time objective.
    """
    validated_distance_matrix = validate_distance_matrix(distance_matrix, problem)
    validated_duration_matrix = validate_duration_matrix(duration_matrix, problem)
    if type(time_limit_seconds) is not int or time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds deve ser um inteiro positivo")

    node_count = len(validated_distance_matrix)
    vehicle_count = len(problem.vehicles)
    manager = pywrapcp.RoutingIndexManager(node_count, vehicle_count, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return validated_distance_matrix[from_node][to_node]

    distance_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(distance_callback_index)

    demands = [0, *(delivery.demand for delivery in problem.deliveries)]

    def demand_callback(from_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        return demands[from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,
        [vehicle.capacity for vehicle in problem.vehicles],
        True,
        "Capacity",
    )

    def duration_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        travel_minutes = validated_duration_matrix[from_node][to_node]
        service_minutes = 0 if from_node == 0 else DELIVERY_SERVICE_DURATION_MINUTES
        return service_minutes + travel_minutes

    duration_callback_index = routing.RegisterTransitCallback(duration_callback)
    opening_minute = problem.operating_hours.start_minute
    closing_minute = problem.operating_hours.end_minute
    routing.AddDimension(
        duration_callback_index,
        closing_minute - opening_minute,
        closing_minute,
        False,
        "Time",
    )
    time_dimension = routing.GetDimensionOrDie("Time")

    for delivery_index, delivery in enumerate(problem.deliveries, start=1):
        service_start = time_dimension.CumulVar(manager.NodeToIndex(delivery_index))
        service_start.SetRange(
            delivery.time_window.start_minute,
            delivery.time_window.end_minute - DELIVERY_SERVICE_DURATION_MINUTES,
        )

    for vehicle_index in range(vehicle_count):
        start_time = time_dimension.CumulVar(routing.Start(vehicle_index))
        return_time = time_dimension.CumulVar(routing.End(vehicle_index))
        start_time.SetRange(opening_minute, closing_minute)
        return_time.SetRange(opening_minute, closing_minute)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = time_limit_seconds

    solution = routing.SolveWithParameters(search_parameters)
    status_code = routing.status()
    if solution is None:
        return SolveResult(
            status=_status_without_solution(status_code),
            routes=None,
            total_distance_meters=None,
            ortools_status_code=status_code,
        )

    routes = _extract_routes(
        problem,
        validated_distance_matrix,
        validated_duration_matrix,
        manager,
        routing,
        solution,
    )
    _verify_schedule(problem, validated_duration_matrix, routes)
    return SolveResult(
        status=SolverStatus.SOLUTION_FOUND,
        routes=routes,
        total_distance_meters=sum(route.distance_meters for route in routes),
        ortools_status_code=status_code,
    )


def _verify_schedule(
    problem: Problem,
    duration_matrix: list[list[int]],
    routes: tuple[VehicleRoute, ...],
) -> None:
    """Check the concrete schedule extracted from the OR-Tools assignment."""
    opening_minute = problem.operating_hours.start_minute
    closing_minute = problem.operating_hours.end_minute
    seen_delivery_indices = []

    for route in routes:
        if not opening_minute <= route.departure_minute <= closing_minute:
            raise RuntimeError("Partida fora do expediente")
        if not opening_minute <= route.return_minute <= closing_minute:
            raise RuntimeError("Retorno fora do expediente")

        previous_point = route.points[0]
        previous_finish = route.departure_minute
        if previous_point.kind != "depot":
            raise RuntimeError("Rota deve começar no depósito")

        for point in route.points[1:]:
            earliest_time = (
                previous_finish
                + duration_matrix[previous_point.matrix_index][point.matrix_index]
            )
            if point.kind == "delivery":
                if (
                    point.service_start_minute is None
                    or point.service_end_minute is None
                ):
                    raise RuntimeError("Entrega sem horário concreto de atendimento")
                delivery = problem.deliveries[point.matrix_index - 1]
                if point.service_end_minute != (
                    point.service_start_minute + DELIVERY_SERVICE_DURATION_MINUTES
                ):
                    raise RuntimeError("Duração de atendimento inconsistente")
                if point.service_start_minute < earliest_time:
                    raise RuntimeError("Atendimento começa antes da chegada possível")
                if (
                    point.service_start_minute < delivery.time_window.start_minute
                    or point.service_end_minute > delivery.time_window.end_minute
                ):
                    raise RuntimeError("Atendimento fora da janela efetiva")
                seen_delivery_indices.append(point.matrix_index)
                previous_finish = point.service_end_minute
            else:
                if (
                    point.service_start_minute is not None
                    or point.service_end_minute is not None
                ):
                    raise RuntimeError("Depósito não pode ter horário de atendimento")
                if point is not route.points[-1]:
                    raise RuntimeError("A rota só pode retornar ao depósito no final")
                if route.return_minute < earliest_time:
                    raise RuntimeError("Retorno antes do tempo mínimo de viagem")
                previous_finish = route.return_minute
            previous_point = point

        if route.points[-1].kind != "depot":
            raise RuntimeError("Rota deve terminar no depósito")

    expected_delivery_indices = list(range(1, len(problem.deliveries) + 1))
    if sorted(seen_delivery_indices) != expected_delivery_indices:
        raise RuntimeError("A solução não atende cada entrega exatamente uma vez")
