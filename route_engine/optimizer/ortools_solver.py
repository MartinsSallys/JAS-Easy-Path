"""Capacitated vehicle routing integration using Google OR-Tools."""

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from route_engine.domain.models import Problem
from route_engine.optimizer.results import (
    RoutePoint,
    SolveResult,
    SolverStatus,
    VehicleRoute,
)
from route_engine.services.distance_matrix import validate_distance_matrix


def _status_without_solution(status_code: int) -> SolverStatus:
    statuses = routing_enums_pb2.RoutingSearchStatus
    if status_code == statuses.ROUTING_INFEASIBLE:
        return SolverStatus.INFEASIBLE
    if status_code == statuses.ROUTING_INVALID:
        return SolverStatus.INVALID_MODEL
    return SolverStatus.NO_SOLUTION


def _point_for_index(problem: Problem, matrix_index: int) -> RoutePoint:
    if matrix_index == 0:
        return RoutePoint(kind="depot", id=problem.depot.id, matrix_index=0)

    delivery = problem.deliveries[matrix_index - 1]
    return RoutePoint(
        kind="delivery",
        id=delivery.id,
        matrix_index=matrix_index,
    )


def _extract_routes(
    problem: Problem,
    matrix: list[list[int]],
    manager: pywrapcp.RoutingIndexManager,
    routing: pywrapcp.RoutingModel,
    solution: pywrapcp.Assignment,
) -> tuple[VehicleRoute, ...]:
    routes = []
    for vehicle_index, vehicle in enumerate(problem.vehicles):
        points = []
        load = 0
        distance_meters = 0
        routing_index = routing.Start(vehicle_index)

        while True:
            matrix_index = manager.IndexToNode(routing_index)
            points.append(_point_for_index(problem, matrix_index))
            if routing.IsEnd(routing_index):
                break

            next_routing_index = solution.Value(routing.NextVar(routing_index))
            next_matrix_index = manager.IndexToNode(next_routing_index)
            distance_meters += matrix[matrix_index][next_matrix_index]
            if matrix_index != 0:
                load += problem.deliveries[matrix_index - 1].demand
            routing_index = next_routing_index

        routes.append(
            VehicleRoute(
                vehicle_id=vehicle.id,
                points=tuple(points),
                load=load,
                distance_meters=distance_meters,
            )
        )

    return tuple(routes)


def solve_routes(
    problem: Problem,
    matrix: object,
    *,
    time_limit_seconds: int = 1,
) -> SolveResult:
    """Solve the CVRP for a validated Problem and a separate distance matrix.

    This distance-and-capacity model does not enforce operating hours,
    delivery windows, service duration, waiting, or return deadlines.
    Uses matrix positions ``[depot, *problem.deliveries]`` and returns routes
    with application IDs only as labels. A positive integer time limit is
    configurable; the default is one second.
    """
    validated_matrix = validate_distance_matrix(matrix, problem)
    if type(time_limit_seconds) is not int or time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds deve ser um inteiro positivo")

    node_count = len(validated_matrix)
    vehicle_count = len(problem.vehicles)
    manager = pywrapcp.RoutingIndexManager(node_count, vehicle_count, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return validated_matrix[from_node][to_node]

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
        validated_matrix,
        manager,
        routing,
        solution,
    )
    return SolveResult(
        status=SolverStatus.SOLUTION_FOUND,
        routes=routes,
        total_distance_meters=sum(route.distance_meters for route in routes),
        ortools_status_code=status_code,
    )
